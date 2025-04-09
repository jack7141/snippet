import json
import ast
import pandas as pd
from math import sqrt
from collections import OrderedDict
from django.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from common.decorators import cached_property
from dateutil.relativedelta import relativedelta

from api.bases.funds.models import Trading as fund_Trading
from api.bases.etf_kr.models import Trading as etf_kr_Trading

class JSONField(models.TextField):
    def to_python(self, value):
        if value == "":
            return None

        try:
            if isinstance(value, str):
                return json.loads(value)
        except ValueError:
            pass
        return value

    def from_db_value(self, value, *args):
        return self.to_python(value)

    def get_db_prep_save(self, value, *args, **kwargs):
        if value == "":
            return None
        if isinstance(value, dict):
            value = json.dumps(value, cls=DjangoJSONEncoder)
        return value


class ListField(models.TextField):

    def to_python(self, value):
        if not value:
            value = []

        if isinstance(value, list):
            return value

        try:
            return ast.literal_eval(value)
        except ValueError:
            return json.loads(value)

    def from_db_value(self, value, *args):
        return self.to_python(value)

    def get_db_prep_save(self, value, *args, **kwargs):
        if value == "":
            return None
        if isinstance(value, list):
            value = json.dumps(value, cls=DjangoJSONEncoder)
        return value

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_prep_value(value)


class AnalyticsMixin(object):
    type_property = 'type'
    summary_periods = {
        '1d': relativedelta(days=1),
        '1m': relativedelta(months=1),
        '3m': relativedelta(months=3),
        '6m': relativedelta(months=6),
        '1y': relativedelta(years=1),
        '3y': relativedelta(years=3),
    }

    def get_trading_type(self):
        _type = None
        for prop in self.type_property.split('.'):
            if not _type:
                _type = getattr(self, prop)
            else:
                _type = getattr(_type, prop)

        return str(_type)

    def set_trading_dataframe(self, date, end_date=timezone.now()):
        queryset = self.trading_queryset \
            .filter(symbol__in=list(self.symbols), date__gte=date, date__lte=end_date) \
            .values('symbol', 'date', 'adjusted_nav')

        df = pd.DataFrame(queryset)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df['nav'] = df['adjusted_nav'].astype(float)
            df = df.set_index('date')
            df = pd.DataFrame({symbol: df[df.symbol == symbol].nav for symbol in self.symbols})
        self._set_trading_dataframe(df)

        return df

    def set_slice_dataframe(self, _from, _to):
        self._set_trading_dataframe(self.trading_dataframe[_from:_to])

    def reindex_dataframe(self, *args, **kwargs):
        self._set_trading_dataframe(self.trading_dataframe.reindex(*args, **kwargs))

    def _set_trading_dataframe(self, df):
        setattr(self, '_trading_dataframe', df)
        self.clear_calc()

    def clear_calc(self):
        for key in ['evaluation_amount',
                    'daily_returns',
                    'cumulative_returns',
                    'max_drawdown',
                    'annual_volatility',
                    'annual_return',
                    'sharp_ratio']:
            if hasattr(self, '_' + key):
                delattr(self, '_' + key)

    @cached_property
    def trading_queryset(self):
        _type = self.get_trading_type()
        _Trading = globals().get(_type + '_Trading')
        field_defs = {
            'symbol': ['isin'],
            'adjusted_nav': ['nav', 'price']
        }
        queryset = _Trading.objects.all()

        for field_name, annotate_defs in field_defs.items():
            try:
                _Trading._meta.get_field(field_name)
            except models.FieldDoesNotExist:
                for annotate_field in annotate_defs:
                    if annotate_field in _Trading._meta._forward_fields_map:
                        queryset = queryset.annotate(**{field_name: models.F(annotate_field)})
        return queryset

    @property
    def trading_dataframe(self):
        if not hasattr(self, '_trading_dataframe'):
            raise AssertionError('You should call `.get_trading_dataframe(date)` first.')
        return getattr(self, '_trading_dataframe')

    @cached_property
    def symbols(self):
        return []

    @cached_property
    def evaluation_amount(self, **kwargs):
        df = self.trading_dataframe.copy()
        return df.dropna()

    @cached_property
    def daily_returns(self):
        return self.evaluation_amount.sum(axis=1).pct_change().fillna(0)

    @cached_property
    def cumulative_returns(self):
        return (self.daily_returns + 1).cumprod() - 1

    @cached_property
    def max_drawdown(self):
        hpr = self.cumulative_returns + 1
        return (hpr / hpr.cummax() - 1).min()

    @cached_property
    def annual_volatility(self):
        return self.daily_returns.std() * sqrt(250)

    @cached_property
    def annual_return(self):
        df = self.cumulative_returns.copy()
        return ((df + 1) ** (250 / (len(df) - 1)) - 1)[-1]

    @cached_property
    def sharp_ratio(self):
        if self.annual_return > 0:
            return self.annual_return / self.annual_volatility
        else:
            return self.annual_return * self.annual_volatility

    def get_group_returns(self, term_groups):
        result = OrderedDict()
        latest = self.evaluation_amount.index[-1]
        start_at = self.cumulative_returns.index[0]

        for k, v in term_groups.items():
            if k == '1d':
                temp = ((self.evaluation_amount.tail(2).sum(axis=1).pct_change() + 1).cumprod() - 1)
                result.update({k: temp[-1]})
            elif start_at < latest - v:
                temp = ((self.evaluation_amount[latest.date() - v:].sum(axis=1).pct_change() + 1).cumprod() - 1)
                result.update({k: temp[-1]})
            elif start_at - relativedelta(weeks=1) < latest - v:
                temp = ((self.evaluation_amount.sum(axis=1).pct_change() + 1).cumprod() - 1)
                result.update({k: temp[-1]})
            else:
                result.update({k: None})
        return result

    def get_summary(self):
        return OrderedDict(self.get_group_returns(self.summary_periods), **{
            'name': self.name,
            'cumulative_return': self.cumulative_returns[-1],
            'annual_return': self.annual_return,
            'annual_volatility': self.annual_volatility,
            'mdd': self.max_drawdown,
            'sharp_ratio': self.sharp_ratio,
        })
