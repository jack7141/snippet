import pandas as pd
from django.db import models


class ClosingPriceQuerySet(models.QuerySet):
    def get_pivoted(self, symbols, from_date, to_date):
        _df = pd.DataFrame(
            self.filter(symbol__in=symbols, busi_date__gte=from_date, busi_date__lte=to_date).values('symbol',
                                                                                                     'busi_date',
                                                                                                     'last'))
        if _df.empty:
            return _df
        pivoted = _df.pivot(columns='symbol', index='busi_date', values='last')
        pivoted.index = pd.to_datetime(pivoted.index)
        pivoted.index = pivoted.index.tz_localize('Asia/Seoul')
        return pivoted
