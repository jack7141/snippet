import pandas as pd
import json
from collections import OrderedDict
from math import sqrt
from dateutil.relativedelta import relativedelta
from common.decorators import cached_property


class AnalyticsInvestment(object):
    working_days = 250
    summary_periods = {
        '1d': relativedelta(days=1),
        '1m': relativedelta(months=1),
        '3m': relativedelta(months=3),
        '6m': relativedelta(months=6),
        '1y': relativedelta(years=1),
        '3y': relativedelta(years=3),
    }

    def __init__(self, data_frame):
        self._data_frame = data_frame

    @cached_property
    def evaluation_amount(self, **kwargs):
        df = self._data_frame.copy()
        eva = df.sum(axis=1)
        return eva

    @cached_property
    def daily_returns(self):
        return self.evaluation_amount.pct_change().fillna(0)

    @cached_property
    def cumulative_returns(self):
        return (self.daily_returns + 1).cumprod() - 1

    @cached_property
    def max_drawdown(self):
        hpr = self.cumulative_returns + 1
        return (hpr / hpr.cummax() - 1).min()

    @cached_property
    def annual_volatility(self):
        return self.daily_returns.std() * sqrt(self.working_days)

    @cached_property
    def annual_return(self):
        df = self.cumulative_returns.copy()
        return ((df + 1) ** (self.working_days / (len(df) - 1)) - 1)[-1]

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
                temp = ((self.evaluation_amount.tail(2).pct_change() + 1).cumprod() - 1)
                result.update({k: temp[-1]})
            elif start_at < latest - v:
                temp = ((self.evaluation_amount[latest.date() - v:].pct_change() + 1).cumprod() - 1)
                result.update({k: temp[-1]})
            elif start_at - relativedelta(weeks=1) < latest - v:
                temp = ((self.evaluation_amount.pct_change() + 1).cumprod() - 1)
                result.update({k: temp[-1]})
            else:
                result.update({k: None})
        return result

    def get_summary(self):
        return OrderedDict(self.get_group_returns(self.summary_periods), **{
            'cumulative_return': self.cumulative_returns[-1],
            'cumulative_returns': json.loads(self.cumulative_returns.to_json()),
            'evaluation_amount': json.loads(self.evaluation_amount.to_json()),
            'min': self.cumulative_returns.min(),
            'max': self.cumulative_returns.max(),
            'mean': self.cumulative_returns.mean(),
            'std': self.cumulative_returns.std(),
            'annual_return': self.annual_return,
            'annual_volatility': self.annual_volatility,
            'mdd': self.max_drawdown,
            'sharp_ratio': self.sharp_ratio,
        })
