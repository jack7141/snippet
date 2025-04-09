import pandas as pd
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from common.exceptions import PreconditionFailed, NoMatchedAccount

BID = '매수'
ASK = '매도'


class QtyQuerySetMixin:
    TICKER_FIELD = 'STOCK_CODE'
    DATE_FIELD = 'DATE'
    TRADE_NAME_FIELD = 'TRADE_NAME'
    PRICE_FIELD = 'PRICE'
    QTY_FIELD = 'QTY'

    @property
    def value_fields(self):
        return [self.TICKER_FIELD, self.DATE_FIELD, self.TRADE_NAME_FIELD, self.QTY_FIELD, self.PRICE_FIELD]

    @property
    def pivot_index(self):
        return self.DATE_FIELD

    @property
    def pivot_columns(self):
        return self.TICKER_FIELD

    @property
    def pivot_values(self):
        return self.QTY_FIELD

    def get_df(self, *values):
        if self.values('account_alias').distinct().count() > 1:
            raise PreconditionFailed({"detail": "calc_trade_qty supports for singe account.trade_set"})
        return pd.DataFrame(self.values(*self.value_fields))

    def calc_qty(self, agg_func=None) -> pd.DataFrame:
        trade_df = self.get_df()
        if trade_df.empty:
            return trade_df

        trade_df.astype({self.QTY_FIELD: 'float', self.PRICE_FIELD: 'float'})
        td_qty_group_by = trade_df.groupby([self.DATE_FIELD, self.TICKER_FIELD])
        if agg_func is None:
            td_qty_df = td_qty_group_by.sum()
        else:
            td_qty_df = td_qty_group_by.apply(agg_func)

        pivoted = td_qty_df.reset_index().pivot(index=self.pivot_index, columns=self.pivot_columns,
                                                values=self.pivot_values)
        pivoted.index.name = 'base_date'
        return pivoted.fillna(0)


class TradeQuerySet(QtyQuerySetMixin, models.QuerySet):
    TICKER_FIELD = 'st_stock_code'
    DATE_FIELD = 'trd_date'
    TRADE_NAME_FIELD = 'j_name'
    QTY_FIELD = 'quantity'
    PRICE_FIELD = 'trd_p'

    def calc_settle_qty(self):
        def _agg_daily_trade(row):
            row = row[row[self.QTY_FIELD] > 0].astype({self.QTY_FIELD: 'float'})
            row.loc[row[self.TRADE_NAME_FIELD].str.startswith(BID), self.QTY_FIELD] = row.loc[
                row[self.TRADE_NAME_FIELD].str.endswith(BID), self.QTY_FIELD]
            row.loc[row[self.TRADE_NAME_FIELD].str.startswith(ASK), self.QTY_FIELD] = -row.loc[
                row[self.TRADE_NAME_FIELD].str.endswith(ASK), self.QTY_FIELD]
            return row.sum(numeric_only=True)

        return self.calc_qty(agg_func=_agg_daily_trade)


class ExecutionQuerySet(QtyQuerySetMixin, models.QuerySet):
    TICKER_FIELD = 'code'
    DATE_FIELD = 'order_date'
    TRADE_NAME_FIELD = 'trade_sec_name'
    QTY_FIELD = 'exec_qty'
    PRICE_FIELD = 'exec_price'

    def calc_exec_qty(self):
        def _agg_daily_exec(row):
            row = row[row[self.QTY_FIELD] > 0]
            row.loc[row[self.TRADE_NAME_FIELD].str.startswith(BID), self.QTY_FIELD] = row.loc[
                row[self.TRADE_NAME_FIELD].str.startswith(BID), self.QTY_FIELD]
            row.loc[row[self.TRADE_NAME_FIELD].str.startswith(ASK), self.QTY_FIELD] = -row.loc[
                row[self.TRADE_NAME_FIELD].str.startswith(ASK), self.QTY_FIELD]
            agg_row = row.sum(numeric_only=True)
            agg_row[self.PRICE_FIELD] = (row[self.PRICE_FIELD] * row[self.QTY_FIELD]).mean()
            return agg_row

        return self.calc_qty(agg_func=_agg_daily_exec)


class HoldingQuerySet(models.QuerySet):
    def to_df(self):
        registered = pd.DataFrame(self.values())
        if registered.empty:
            return registered
        registered = registered.pivot(index='created_at', columns='code', values='shares').fillna(0)
        registered.index = registered.index.tz_convert(tz=settings.TIME_ZONE)
        return registered.resample('D').ffill()

    def calc_balance_usd(self, price_queryset) -> pd.Series:
        qty_df = self.to_df()
        from_date, to_date = qty_df.index[0], qty_df.index[-1]
        price_df = price_queryset.get_pivoted(symbols=qty_df.columns, from_date=from_date, to_date=to_date)
        price_df.index = price_df.index.shift(1, 'D')
        balance_sr = (qty_df * price_df.resample('D').ffill().astype(float)).sum(axis=1).dropna()
        return balance_sr


class AccountDetectionManger(models.Manager):
    def get_or_404_raise(self, filter_kwargs):
        try:
            return self.model.get(self, **filter_kwargs)
        except ObjectDoesNotExist:
            raise NoMatchedAccount


