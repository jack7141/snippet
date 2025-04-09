from __future__ import unicode_literals

from django.db import models
from datetime import datetime
from dateutil.relativedelta import relativedelta
from common.asset_enums import ASSET_CODES

__all__ = [
    'Profile', 'Trading'
]


class Profile(models.Model):
    isin = models.CharField(db_column='ISIN', primary_key=True, max_length=12)
    symbol = models.CharField(db_column='Symbol', max_length=10, blank=True, null=True)
    name = models.CharField(db_column='AssetName', max_length=256, blank=True, null=True)
    local_asset_name = models.CharField(db_column='LocalAssetName', max_length=256, blank=True, null=True)
    inception_date = models.DateField(db_column='InceptionDate', blank=True, null=True)
    nav_start_date = models.DateField(db_column='NAVStartDate', blank=True, null=True)
    issuer_name = models.CharField(db_column='IssuerName', max_length=64, blank=True, null=True)
    underlying_index_name = models.CharField(db_column='UnderlyingIndexName', max_length=128, blank=True, null=True)
    replication_method = models.CharField(db_column='ReplicationMethod', max_length=16, blank=True, null=True)
    leverage_factor = models.CharField(db_column='LeverageFactor', max_length=10, blank=True, null=True)
    etp_type = models.CharField(db_column='ETPType', max_length=8, blank=True, null=True)
    underlying_asset_1st = models.CharField(db_column='UnderlyingAsset1st', max_length=32, blank=True, null=True)
    underlying_asset_2nd = models.CharField(db_column='UnderlyingAsset2nd', max_length=32, blank=True, null=True)
    underlying_asset_3rd = models.CharField(db_column='UnderlyingAsset3rd', max_length=32, blank=True, null=True)
    underlying_market_1st = models.CharField(db_column='UnderlyingMarket1st', max_length=32, blank=True, null=True)
    underlying_market_2nd = models.CharField(db_column='UnderlyingMarket2nd', max_length=32, blank=True, null=True)
    underlying_market_3rd = models.CharField(db_column='UnderlyingMarket3rd', max_length=32, blank=True, null=True)
    expense_ratio = models.DecimalField(db_column='ExpenseRatio', max_digits=8, decimal_places=4, blank=True, null=True)
    cash_flow_frequency = models.CharField(db_column='CashFlowFrequency', max_length=128, blank=True, null=True)
    taxation = models.CharField(db_column='Taxation', max_length=64, blank=True, null=True)
    liquidity_provider = models.CharField(db_column='LiquidityProvider', max_length=256, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Profile'

    def get_month_ago_trading(self):
        today = datetime.today()
        prev_month = today - relativedelta(months=1)
        return self.trading.filter(date__gte=prev_month).order_by('-date')

    def get_asset_category(self):
        if self.underlying_asset_1st == '주식':
            return ASSET_CODES.stock
        elif self.underlying_asset_1st == '채권':
            return ASSET_CODES.bond
        elif self.underlying_asset_1st == '원자재':
            return ASSET_CODES.commodity
        elif self.underlying_asset_1st in ['부동산', '통화']:
            return ASSET_CODES.alternative
        else:
            return ASSET_CODES.etc


class Trading(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    isin = models.ForeignKey(Profile, related_name='trading', to_field='isin', db_column='ISIN')
    nav = models.DecimalField(db_column='NAV', max_digits=10, decimal_places=2, blank=True, null=True)
    closing_price = models.DecimalField(db_column='ClosingPrice', max_digits=9, decimal_places=0, blank=True, null=True)
    opening_price = models.DecimalField(db_column='OpeningPrice', max_digits=9, decimal_places=0, blank=True, null=True)
    high_price = models.DecimalField(db_column='HighPrice', max_digits=9, decimal_places=0, blank=True, null=True)
    low_price = models.DecimalField(db_column='LowPrice', max_digits=9, decimal_places=0, blank=True, null=True)
    bid_price = models.DecimalField(db_column='BidPrice', max_digits=9, decimal_places=0, blank=True, null=True)
    ask_price = models.DecimalField(db_column='AskPrice', max_digits=9, decimal_places=0, blank=True, null=True)
    vwap = models.DecimalField(db_column='VWAP', max_digits=20, decimal_places=8, blank=True, null=True)
    difference = models.DecimalField(db_column='Difference', max_digits=10, decimal_places=8, blank=True, null=True)
    bid_ask_spread = models.DecimalField(db_column='BidAskSpread', max_digits=15, decimal_places=8, blank=True,
                                         null=True)
    trading_volume = models.DecimalField(db_column='TradingVolume', max_digits=18, decimal_places=0, blank=True,
                                         null=True)
    trading_amount = models.DecimalField(db_column='TradingAmount', max_digits=25, decimal_places=0, blank=True,
                                         null=True)
    fund_flows = models.DecimalField(db_column='FundFlows', max_digits=18, decimal_places=2, blank=True, null=True)
    aum = models.DecimalField(db_column='AUM', max_digits=18, decimal_places=2, blank=True, null=True)
    shares_outstanding = models.DecimalField(db_column='SharesOutstanding', max_digits=18, decimal_places=0, blank=True,
                                             null=True)
    creation_unit = models.DecimalField(db_column='CreationUnit', max_digits=19, decimal_places=5, blank=True,
                                        null=True)
    number_of_holdings = models.DecimalField(db_column='NumberOfHoldings', max_digits=5, decimal_places=0, blank=True,
                                             null=True)
    asset_turnover = models.DecimalField(db_column='AssetTurnover', max_digits=12, decimal_places=8, blank=True,
                                         null=True)
    dividend_yield = models.DecimalField(db_column='DividendYield', max_digits=12, decimal_places=8, blank=True,
                                         null=True)
    market_cap = models.DecimalField(db_column='MarketCap', max_digits=25, decimal_places=0, blank=True, null=True)
    large_cap = models.DecimalField(db_column='LargeCap', max_digits=12, decimal_places=8, blank=True, null=True)
    mid_cap = models.DecimalField(db_column='MidCap', max_digits=12, decimal_places=8, blank=True, null=True)
    small_cap = models.DecimalField(db_column='SmallCap', max_digits=12, decimal_places=8, blank=True, null=True)
    disclosure_index = models.SmallIntegerField(db_column='DisclosureIndex', blank=True, null=True)
    distribution = models.DecimalField(db_column='Distribution', max_digits=9, decimal_places=0, blank=True, null=True)
    record_date = models.DateField(db_column='RecordDate', blank=True, null=True)
    payment_date = models.DateField(db_column='PaymentDate', blank=True, null=True)
    suspend_start_date = models.DateField(db_column='SuspendStartDate', blank=True, null=True)
    suspend_end_date = models.DateField(db_column='SuspendEndDate', blank=True, null=True)
    liquidation_date = models.DateField(db_column='LiquidationDate', blank=True, null=True)
    tax_base_price = models.DecimalField(db_column='TaxBasePrice', max_digits=10, decimal_places=2, blank=True,
                                         null=True)
    ex_date = models.DateField(db_column='ExDate', blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate')

    class Meta:
        managed = False
        db_table = 'Trading'
        unique_together = (('date', 'isin'),)
