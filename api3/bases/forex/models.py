import datetime

import pandas as pd
import requests as req
from django.conf import settings
from django.db import models

from common.behaviors import Timestampable
from .managers import ExchangeRateQuerySet


class ExchangeRate(Timestampable, models.Model):
    objects = ExchangeRateQuerySet.as_manager()

    currency_code = models.CharField(help_text="외화코드(ISO4217)", max_length=3)
    base_date = models.DateField(help_text="기준일")
    open = models.DecimalField(max_digits=15, decimal_places=4, help_text="오픈(매매기준율)")
    close = models.DecimalField(max_digits=15, decimal_places=4, help_text="종가", null=True)
    high = models.DecimalField(max_digits=15, decimal_places=4, null=True)
    low = models.DecimalField(max_digits=15, decimal_places=4, null=True)

    class Meta:
        unique_together = ('currency_code', 'base_date')

    @staticmethod
    def _request_exchange_rate(base_date: datetime.date):
        if isinstance(base_date, datetime.date):
            base_date = base_date.strftime('%Y%m%d')
        resp = req.get(f"{settings.TR_BACKEND}/api/v1/kb/exchange/rate/{base_date}")
        resp.raise_for_status()
        return resp.json()

    @classmethod
    def get_exchange_rate(cls, base_date):
        resp = cls._request_exchange_rate(base_date=base_date)
        exchange_df = pd.DataFrame(resp.get('currencies', []))
        exchange = {
            'open': None, 'close': None, 'high': None, 'low': None
        }
        if not exchange_df.empty:
            exchange['open'], exchange['close'] = exchange_df.transaction.iloc[0], exchange_df.transaction.iloc[-1]
            exchange['high'], exchange['low'] = max(exchange_df.transaction), min(exchange_df.transaction)
        return exchange

    @classmethod
    def init_by_tr_response(cls, currency_code: str, base_date: datetime.date):
        init_kwargs = {
            'base_date': base_date,
            'currency_code': currency_code
        }
        init_kwargs.update(cls.get_exchange_rate(base_date=base_date))
        return cls(**init_kwargs)
