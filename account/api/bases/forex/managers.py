import pandas as pd
from django.conf import settings
from django.db import models


class ExchangeRateQuerySet(models.QuerySet):
    def to_df(self, value='close'):
        registered = pd.DataFrame(self.values())
        if registered.empty:
            return registered
        registered = registered.pivot(index='base_date', columns='currency_code', values=value).fillna(0)
        registered.index = pd.to_datetime(registered.index)
        registered.index = registered.index.tz_localize(tz=settings.TIME_ZONE)
        return registered.resample('D').ffill()
