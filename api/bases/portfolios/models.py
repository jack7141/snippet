from django.db import models

from common import models as c_models
from common.decorators import cached_property
from common.models import AnalyticsMixin

from api.bases.etf_kr.models import Profile as etf_kr_Profile
from api.bases.etf_us.models import Profile as etf_us_Profile
from api.bases.funds.models import Operation as fund_Operation


class PortfolioManager(models.Manager):
    def get_portfolio(self, universe_index, port_date, risk_type=None):
        queryset = self.filter(port_type__universe_index__universe_index=universe_index,
                               port_type__risk_type=risk_type,
                               port_date__lte=port_date)

        if queryset.exists():
            return queryset.filter(port_date=queryset.first().port_date)

        return queryset

    def get_available_port_date(self, universe_index, port_date, risk_type=None):
        pass


class PortfolioUniverse(models.Model):
    universe_name = models.CharField(max_length=20, blank=True, null=True)
    universe_index = models.SmallIntegerField(primary_key=True)
    display_name = models.CharField(max_length=50, blank=True, null=True, db_column='display')
    engine_type = models.CharField(max_length=10, blank=True, null=True)
    is_operating = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'portfolio_universe'


class PortfolioType(models.Model):
    port_type_index = models.IntegerField(primary_key=True)
    port_type_name = models.CharField(max_length=30, blank=True, null=True)
    universe_index = models.ForeignKey(PortfolioUniverse, db_column='universe_index', related_name='port_types')
    risk_type = models.SmallIntegerField(blank=True, null=True)
    risk_name = models.CharField(max_length=20, blank=True, null=True)
    strategy_code = models.SmallIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'portfolio_type'
        unique_together = ('port_type_index', 'universe_index',)


class PortfolioDaily(AnalyticsMixin, models.Model):
    objects = PortfolioManager()

    port_seq = models.BigIntegerField(primary_key=True)
    port_date = models.DateField()
    port_type = models.ForeignKey(PortfolioType, db_column='port_type')
    bw_type = models.IntegerField()
    port_data = c_models.ListField()
    update_date = models.DateTimeField()
    description = models.TextField()

    class Meta:
        managed = False
        db_table = 'bluewhale_portfolio'
        ordering = ('-port_date',)

    @property
    def type(self):
        if not hasattr(self, '_type'):
            setattr(self, '_type', self.port_type.universe_index.engine_type.lower())
        return self._type

    @property
    def tendency(self):
        if not hasattr(self, '_tendency'):
            setattr(self, '_tendency', self.port_type.risk_type)
        return self._tendency

    @property
    def universe_index(self):
        return int(str(self.port_seq)[8:12])

    @cached_property
    def symbols(self):
        return [item.get('code') for item in self.port_data if item.get('code') != '000000000000']

    def get_port_data(self):
        # Note. asset category 자체분류한 결과값으로 port_data 제공처리
        port_data = self.port_data
        symbols = [item.get('code') for item in port_data]
        asset_category = {}

        if self.type == 'fund':
            queryset = fund_Operation.objects.filter(symbol__in=symbols, end_date__isnull=True)
            asset_category = {query.symbol: query.get_asset_category() for query in queryset.iterator()}
        elif self.type == 'etf_kr':
            queryset = etf_kr_Profile.objects.filter(isin__in=symbols)
            asset_category = {query.isin: query.get_asset_category() for query in queryset.iterator()}
        elif self.type == 'etf_us':
            queryset = etf_us_Profile.objects.filter(symbol__in=symbols)
            asset_category = {query.symbol: query.get_asset_category() for query in queryset.iterator()}

        for item in port_data:
            if item.get('code') == '000000000000':
                item.update({'asset_category': 'LIQ'})
            else:
                item.update({'asset_category': asset_category.get(item.get('code'), None)})

        return port_data

    def evaluation_amount(self, base_amount=1000000):
        df = self.trading_dataframe.copy()
        df = df.dropna()
        if df.empty:
            return df
        items = [{'asset': item.get('code'), 'weight': item.get('weight')} for item in self.port_data]
        for item in items:
            if item['asset'] == '000000000000':
                df[item['asset']] = ((base_amount * item['weight']) / 1)
            else:
                df[item['asset']] = ((base_amount * item['weight']) / (df[item['asset']].iloc[0])) * df[item['asset']]

        return df.dropna()

    @cached_property
    def description_list(self):
        description_list = self.description.strip().splitlines()
        return list(filter(None, description_list))


class FundCalendar(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    day_code = models.CharField(db_column='DayCode', max_length=1, blank=True, null=True)
    is_holiday = models.CharField(db_column='IsHoliday', max_length=1, blank=True, null=True)
    day_name = models.CharField(db_column='DayName', max_length=20, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Calendar'


class ETFCalendar(models.Model):
    market_holiday_id = models.CharField(db_column='MarketHolidayId', primary_key=True, max_length=10)
    date = models.DateField(db_column='MarketHolidayDate')
    country_id = models.CharField(db_column='CountryId', max_length=10)
    country_name = models.CharField(db_column='CountryName', max_length=40)
    update_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'ETCHoliday'