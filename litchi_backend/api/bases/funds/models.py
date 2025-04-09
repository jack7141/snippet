# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from __future__ import unicode_literals

from django.db import models
from datetime import datetime
from dateutil.relativedelta import relativedelta
from common.asset_enums import ASSET_CODES

__all__ = [
    'Accounting', 'Bmoperation', 'Bmtrading', 'Calculationterm', 'Calendar', 'FountAssetCategory', 'Category',
    'Company', 'Operation', 'Holding', 'Fee', 'Performance', 'Portfolio', 'Process', 'Rating', 'Redemption',
    'Returns', 'Sales', 'Sector', 'Style', 'Terms', 'TermsReturn', 'Trading'
]


###############
# Fund Models #
###############
class Accounting(models.Model):
    symbol = models.CharField(db_column='Symbol', max_length=12, primary_key=True)
    start_date = models.DateField(db_column='StartDate', primary_key=True)
    end_date = models.DateField(db_column='EndDate', primary_key=True)
    type_code = models.CharField(db_column='TypeCode', max_length=2, primary_key=True)
    aum_on_settlement = models.DecimalField(db_column='AUMOnSettlement', max_digits=18, decimal_places=0, blank=True,
                                            null=True)
    nav_on_settlement = models.DecimalField(db_column='NAVOnSettlement', max_digits=22, decimal_places=12, blank=True,
                                            null=True)
    nav_after_dividend = models.DecimalField(db_column='NAVAfterDividend', max_digits=22, decimal_places=12, blank=True,
                                             null=True)
    dividend_rate = models.DecimalField(db_column='DividendRate', max_digits=22, decimal_places=12, blank=True,
                                        null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Accounting'
        unique_together = (('symbol', 'start_date', 'end_date', 'type_code'),)


class Bmoperation(models.Model):
    code = models.CharField(db_column='Code', primary_key=True, max_length=10)
    name = models.CharField(db_column='Name', max_length=100, blank=True, null=True)
    is_used = models.CharField(db_column='IsUsed', max_length=1, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'BMOperation'


class Bmtrading(models.Model):
    date = models.DateField(db_column='Date', primary_key=True)
    bm_code = models.CharField(db_column='BMCode', max_length=10, primary_key=True)
    bm_daily_return = models.DecimalField(db_column='BMDailyReturn', max_digits=22, decimal_places=12, blank=True,
                                          null=True)
    end_index = models.DecimalField(db_column='EndIndex', max_digits=22, decimal_places=12, blank=True, null=True)
    open_index = models.DecimalField(db_column='OpenIndex', max_digits=22, decimal_places=12, blank=True, null=True)
    high_index = models.DecimalField(db_column='HighIndex', max_digits=22, decimal_places=12, blank=True, null=True)
    low_index = models.DecimalField(db_column='LowIndex', max_digits=22, decimal_places=12, blank=True, null=True)
    trading_volume = models.DecimalField(db_column='TradingVolume', max_digits=18, decimal_places=0, blank=True,
                                         null=True)
    trading_amount = models.DecimalField(db_column='TradingAmount', max_digits=18, decimal_places=0, blank=True,
                                         null=True)
    market_cap = models.DecimalField(db_column='MarketCap', max_digits=18, decimal_places=0, blank=True, null=True)
    sales_date = models.DateField(db_column='SalesDate', blank=True, null=True)
    duration = models.DecimalField(db_column='Duration', max_digits=12, decimal_places=5, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'BMTrading'
        unique_together = (('date', 'bm_code'),)


class Calculationterm(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    type = models.CharField(db_column='TypeCode', max_length=1, primary_key=True)
    term = models.IntegerField(db_column='Term', primary_key=True)
    start_date = models.DateField(db_column='StartDate', blank=True, null=True)
    end_date = models.DateField(db_column='EndDate', blank=True, null=True)
    bm_start_date = models.DateField(db_column='BMStartDate', blank=True, null=True)
    bm_end_date = models.DateField(db_column='BMEndDate', blank=True, null=True)
    business_day = models.IntegerField(db_column='BusinessDay', blank=True, null=True)
    calendar_day = models.IntegerField(db_column='CalendarDay', blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'CalculationTerm'
        unique_together = (('date', 'type', 'term'),)


class Calendar(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    day_code = models.CharField(db_column='DayCode', max_length=1, blank=True, null=True)
    is_holiday = models.CharField(db_column='IsHoliday', max_length=1, blank=True, null=True)
    day_name = models.CharField(db_column='DayName', max_length=20, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Calendar'


class FountAssetCategory(models.Model):
    category_code = models.CharField(db_column='CategoryCode', primary_key=True, max_length=7)
    asset_category = models.CharField(db_column='AssetCategory', max_length=8)

    class Meta:
        managed = False
        db_table = 'FountAssetCategory'


class Category(models.Model):
    code = models.OneToOneField(FountAssetCategory, to_field='category_code', db_column='Code', primary_key=True)
    name = models.CharField(db_column='Name', max_length=50, blank=True, null=True)
    level = models.IntegerField(db_column='GroupCode', blank=True, null=True)
    description = models.TextField(db_column='Description', blank=True, null=True)
    start_date = models.DateField(db_column='StartDate', blank=True, null=True)
    end_date = models.DateField(db_column='EndDate', blank=True, null=True)
    type = models.CharField(db_column='TypeCode', max_length=1, blank=True, null=True)
    bm_code = models.CharField(db_column='BMCode', max_length=10, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Category'


class Company(models.Model):
    code = models.CharField(db_column='Code', primary_key=True, max_length=3)
    name = models.CharField(db_column='Name', max_length=100, blank=True, null=True)
    type_code = models.CharField(db_column='TypeCode', max_length=10, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Company'


class Operation(models.Model):
    symbol = models.CharField(db_column='Symbol', max_length=12, primary_key=True)
    start_date = models.DateField(db_column='StartDate')
    end_date = models.DateField(db_column='EndDate', blank=True, null=True)
    company_code = models.ForeignKey(Company, to_field='code', db_column='CompanyCode', max_length=3, blank=True,
                                     null=True)
    company_symbol = models.CharField(db_column='CompanySymbol', max_length=12, blank=True, null=True)
    name = models.CharField(db_column='Name', max_length=500, blank=True, null=True)
    is_private = models.CharField(db_column='IsPrivate', max_length=1, blank=True, null=True)
    category_code = models.ForeignKey(Category, to_field='code', db_column='CategoryCode', blank=True, null=True,
                                      related_name='category_related')
    isin = models.CharField(db_column='ISIN', max_length=20, blank=True, null=True)
    inception_date = models.DateField(db_column='InceptionDate', blank=True, null=True)
    share_class_symbol = models.CharField(db_column='ShareClassSymbol', max_length=12, blank=True, null=True)
    liquidation_date = models.DateField(db_column='LiquidationDate', blank=True, null=True)
    kofia_code = models.CharField(db_column='KOFIACode', max_length=20, blank=True, null=True)
    kofia_change_date = models.DateField(db_column='KOFIAChangeDate', blank=True, null=True)
    bm_code = models.CharField(db_column='BMCode', max_length=10, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Operation'
        unique_together = (('symbol', 'start_date'),)
        ordering = ('symbol', '-start_date',)

    def get_last_2_styles(self):
        return self.styles.all()[:2]

    def get_month_ago_trading(self):
        today = datetime.today()
        prev_month = today - relativedelta(months=1)
        return self.trading.filter(date__gte=prev_month)

    def get_recents(self, relate_name):
        if hasattr(self, relate_name):
            queryset = getattr(self, relate_name)
            if queryset.exists():
                date = queryset.first().date
                return queryset.filter(date=date)
        return []

    def get_recent_holding(self):
        return self.get_recents('holding')

    def get_recent_performance(self):
        return self.get_recents('performance')

    def get_recent_portfolio(self):
        return self.portfolio.first()

    def get_recent_return(self):
        return self.get_recents('returns')

    def get_recent_sale(self):
        return self.get_recents('sales')

    def get_recent_sector(self):
        return self.get_recents('sectors')

    def get_asset_category(self):
        try:
            category = self.category_code_id

            if category[:2] in ['11', '21']:
                return ASSET_CODES.stock
            elif category[:2] in ['12', '13', '22']:
                return ASSET_CODES.bond
            elif category in ['1530010', '2420010']:
                return ASSET_CODES.commodity
            elif category in ['1510010', '1540010', '2410010', '2430010']:
                return ASSET_CODES.alternative
            else:
                return ASSET_CODES.etc

        except:
            print('category none')
            return None


class Holding(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='holding')
    item_index = models.IntegerField(db_column='ItemIndex', primary_key=True)
    code = models.CharField(db_column='Code', max_length=12, primary_key=True)
    type_code = models.CharField(db_column='TypeCode', max_length=2, primary_key=True)
    name = models.CharField(db_column='Name', max_length=100, blank=True, null=True)
    number_of_holding = models.DecimalField(db_column='NumberOfHolding', max_digits=18, decimal_places=0, blank=True,
                                            null=True)
    investment = models.DecimalField(db_column='Investment', max_digits=18, decimal_places=0, blank=True, null=True)
    market_value = models.DecimalField(db_column='MarketValue', max_digits=18, decimal_places=0, blank=True, null=True)
    book_value = models.DecimalField(db_column='BookValue', max_digits=18, decimal_places=0, blank=True, null=True)
    beta = models.DecimalField(db_column='Beta', max_digits=22, decimal_places=12, blank=True, null=True)
    issue_date = models.DateField(db_column='IssueDate', blank=True, null=True)
    due_date = models.DateField(db_column='DueDate', blank=True, null=True)
    duration = models.DecimalField(db_column='Duration', max_digits=22, decimal_places=12, blank=True, null=True)
    credit_rating = models.CharField(db_column='CreditRating', max_length=4, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Holding'
        unique_together = (('date', 'symbol', 'item_index', 'code', 'type_code'),)
        ordering = ['-date', ]


class Fee(models.Model):
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='fees')
    group_code = models.CharField(db_column='GroupCode', max_length=1, primary_key=True)
    type_code = models.CharField(db_column='TypeCode', max_length=2, primary_key=True)
    rate = models.DecimalField(db_column='Rate', max_digits=5, decimal_places=3, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Fee'
        unique_together = (('symbol', 'group_code', 'type_code'),)


class Performance(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    term_type = models.CharField(db_column='TermType', max_length=1, primary_key=True)
    term = models.IntegerField(db_column='Term', primary_key=True)
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='performance')
    average_return = models.DecimalField(db_column='AverageReturn', max_digits=22, decimal_places=12, blank=True,
                                         null=True)
    standard_deviation = models.DecimalField(db_column='StandardDeviation', max_digits=22, decimal_places=12,
                                             blank=True, null=True)
    standard_deviation_rank = models.IntegerField(db_column='StandardDeviationRank', blank=True, null=True)
    standard_deviation_per_rank = models.DecimalField(db_column='StandardDeviationPerRank', max_digits=22,
                                                      decimal_places=12, blank=True, null=True)
    alpha = models.DecimalField(db_column='Alpha', max_digits=22, decimal_places=12, blank=True, null=True)
    alpha_rank = models.IntegerField(db_column='AlphaRank', blank=True, null=True)
    alpha_per_rank = models.DecimalField(db_column='AlphaPerRank', max_digits=22, decimal_places=12, blank=True,
                                         null=True)
    beta = models.DecimalField(db_column='Beta', max_digits=22, decimal_places=12, blank=True, null=True)
    beta_rank = models.IntegerField(db_column='BetaRank', blank=True, null=True)
    beta_per_rank = models.DecimalField(db_column='BetaPerRank', max_digits=22, decimal_places=12, blank=True,
                                        null=True)
    rsquare = models.DecimalField(db_column='RSquare', max_digits=22, decimal_places=12, blank=True, null=True)
    rsquare_rank = models.IntegerField(db_column='RSquareRank', blank=True, null=True)
    rsquare_per_rank = models.DecimalField(db_column='RSquarePerRank', max_digits=22, decimal_places=12, blank=True,
                                           null=True)
    shape_ratio = models.DecimalField(db_column='ShapeRatio', max_digits=22, decimal_places=12, blank=True, null=True)
    shape_ratio_rank = models.IntegerField(db_column='ShapeRatioRank', blank=True, null=True)
    shape_ratio_per_rank = models.DecimalField(db_column='ShapeRatioPerRank', max_digits=22, decimal_places=12,
                                               blank=True, null=True)
    tracking_error = models.DecimalField(db_column='TrackingError', max_digits=22, decimal_places=12, blank=True,
                                         null=True)
    tracking_error_rank = models.IntegerField(db_column='TrackingErrorRank', blank=True, null=True)
    tracking_error_per_rank = models.DecimalField(db_column='TrackingErrorPerRank', max_digits=22, decimal_places=12,
                                                  blank=True, null=True)
    information_ratio = models.DecimalField(db_column='InformationRatio', max_digits=22, decimal_places=12, blank=True,
                                            null=True)
    information_ratio_rank = models.IntegerField(db_column='InformationRatioRank', blank=True, null=True)
    information_ratio_per_rank = models.DecimalField(db_column='InformationRatioPerRank', max_digits=22,
                                                     decimal_places=12, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Performance'
        unique_together = (('date', 'term_type', 'term', 'symbol'),)
        ordering = ['-date', ]


class Portfolio(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='portfolio')
    net_assets = models.DecimalField(db_column='NetAssets', max_digits=22, decimal_places=0, blank=True, null=True)
    stock = models.DecimalField(db_column='Stock', max_digits=22, decimal_places=0, blank=True, null=True)
    foreign_stock = models.DecimalField(db_column='ForeignStock', max_digits=22, decimal_places=0, blank=True,
                                        null=True)
    bond = models.DecimalField(db_column='Bond', max_digits=22, decimal_places=0, blank=True, null=True)
    foreign_bond = models.DecimalField(db_column='ForeignBond', max_digits=22, decimal_places=0, blank=True, null=True)
    fund = models.DecimalField(db_column='Fund', max_digits=22, decimal_places=0, blank=True, null=True)
    liquidity = models.DecimalField(db_column='Liquidity', max_digits=22, decimal_places=0, blank=True, null=True)
    stock_futures = models.DecimalField(db_column='StockFutures', max_digits=22, decimal_places=0, blank=True,
                                        null=True)
    bond_futures = models.DecimalField(db_column='BondFutures', max_digits=22, decimal_places=0, blank=True, null=True)
    duration = models.DecimalField(db_column='Duration', max_digits=22, decimal_places=12, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Portfolio'
        unique_together = (('date', 'symbol'),)
        ordering = ['-date', ]


class Process(models.Model):
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='processes')
    item_index = models.IntegerField(db_column='ItemIndex', primary_key=True)
    type_code = models.CharField(db_column='TypeCode', max_length=2, blank=True, null=True)
    base_time = models.CharField(db_column='BaseTime', max_length=5, blank=True, null=True)
    nav_before = models.CharField(db_column='NAVBefore', max_length=2, blank=True, null=True)
    trade_before = models.CharField(db_column='TradeBefore', max_length=2, blank=True, null=True)
    nav_after = models.CharField(db_column='NAVAfter', max_length=2, blank=True, null=True)
    trade_after = models.CharField(db_column='TradeAfter', max_length=2, blank=True, null=True)
    description = models.TextField(db_column='Description', blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'TransactionDate'
        unique_together = (('symbol', 'item_index'),)


class Rating(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='ratings')
    term = models.IntegerField(db_column='Term', primary_key=True)
    rating = models.IntegerField(db_column='Rating', blank=True, null=True)
    score = models.DecimalField(db_column='Score', max_digits=22, decimal_places=12, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Rating'
        unique_together = (('date', 'symbol', 'term'),)


class Redemption(models.Model):
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='redemption')
    item_index = models.IntegerField(db_column='ItemIndex', primary_key=True)
    start_date = models.DateField(db_column='StartDate', blank=True, null=True)
    from_count = models.IntegerField(db_column='FromCount', blank=True, null=True)
    over_type_code = models.CharField(db_column='OverTypeCode', max_length=2, blank=True, null=True)
    to_count = models.IntegerField(db_column='ToCount', blank=True, null=True)
    under_type_code = models.CharField(db_column='UnderTypeCode', max_length=2, blank=True, null=True)
    redemption_type_code = models.CharField(db_column='RedemptionTypeCode', max_length=2, blank=True, null=True)
    rate = models.DecimalField(db_column='Rate', max_digits=5, decimal_places=2, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Redemption'
        unique_together = (('symbol', 'item_index'),)


class Returns(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    term_type = models.CharField(db_column='TermType', max_length=1, primary_key=True)
    term = models.IntegerField(db_column='Term', primary_key=True)
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='returns')
    term_return_rank = models.DecimalField(db_column='TermReturnRank', max_digits=7, decimal_places=0, blank=True,
                                           null=True)
    term_return_per_rank = models.DecimalField(db_column='TermReturnPerRank', max_digits=22, decimal_places=15,
                                               blank=True, null=True)
    term_return = models.DecimalField(db_column='TermReturn', max_digits=22, decimal_places=15, blank=True, null=True)
    bm_term_return = models.DecimalField(db_column='BMTermReturn', max_digits=22, decimal_places=15, blank=True,
                                         null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'TermReturn'
        unique_together = (('date', 'term_type', 'term', 'symbol'),)
        ordering = ['-date', ]


class Sales(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='sales')
    company_code = models.CharField(db_column='CompanyCode', max_length=3, primary_key=True)
    amount = models.CharField(db_column='Amount', max_length=5, blank=True, null=True)
    portion = models.CharField(db_column='Portion', max_length=2, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Sales'
        unique_together = (('date', 'symbol', 'company_code'),)
        ordering = ['-date', ]


class Sector(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='sectors')
    code = models.CharField(db_column='Code', max_length=3, primary_key=True)
    name = models.CharField(db_column='Name', max_length=50, blank=True, null=True)
    portion = models.DecimalField(db_column='Portion', max_digits=25, decimal_places=20, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Sector'
        unique_together = (('date', 'symbol', 'code'),)
        ordering = ['-date', ]


class Style(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='styles')
    type = models.CharField(db_column='TypeCode', max_length=2, primary_key=True)
    box_type = models.CharField(db_column='BoxType', max_length=1, primary_key=True)
    size = models.DecimalField(db_column='SizeStyle', max_digits=22, decimal_places=12, blank=True, null=True)
    value = models.CharField(db_column='ValueStyle', max_length=1, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'StyleBox'
        unique_together = (('date', 'symbol', 'type', 'box_type'),)
        ordering = ['-date', ]


class Terms(models.Model):
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='terms')
    type_code = models.CharField(db_column='TypeCode', max_length=2, primary_key=True)
    description = models.TextField(db_column='Description', blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Terms'
        unique_together = (('symbol', 'type_code'),)


class TermsReturn(models.Model):
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='terms_return')
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    term_type = models.CharField(db_column='TermType', max_length=1, primary_key=True)
    term = models.IntegerField(db_column='Term')
    term_return_rank = models.DecimalField(db_column='TermReturnRank', max_digits=7, decimal_places=0)
    term_return_per_rank = models.DecimalField(db_column='TermReturnPerRank', max_digits=22, decimal_places=15)
    term_return = models.DecimalField(db_column='TermReturn', max_digits=22, decimal_places=15)
    bm_term_retrun = models.DecimalField(db_column='BMTermReturn', max_digits=22, decimal_places=15)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'TermReturn'


class Trading(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    symbol = models.ForeignKey(Operation, to_field='symbol', db_column='Symbol', related_name='trading')

    company_code = models.ForeignKey(Company, to_field='code', db_column='CompanyCode', max_length=3, blank=True,
                                     null=True)
    aum = models.DecimalField(db_column='AUM', max_digits=20, decimal_places=0, blank=True, null=True)
    total_shares = models.DecimalField(db_column='TotalShares', max_digits=20, decimal_places=0, blank=True, null=True)
    nav = models.DecimalField(db_column='NAV', max_digits=22, decimal_places=15, blank=True, null=True)
    adjusted_nav = models.DecimalField(db_column='AdjustedNAV', max_digits=22, decimal_places=15, blank=True, null=True)
    net_assets = models.DecimalField(db_column='NetAssets', max_digits=20, decimal_places=0, blank=True, null=True)
    daily_return = models.DecimalField(db_column='DailyReturn', max_digits=22, decimal_places=15, blank=True, null=True)
    bm_daily_return = models.DecimalField(db_column='BMDailyReturn', max_digits=22, decimal_places=15, blank=True,
                                          null=True)
    total_return_index = models.DecimalField(db_column='TotalReturnIndex', max_digits=22, decimal_places=15, blank=True,
                                             null=True)
    bm_total_return_index = models.DecimalField(db_column='BMTotalReturnIndex', max_digits=22, decimal_places=15,
                                                blank=True, null=True)

    category_code = models.ForeignKey(Category, to_field='code', db_column='CategoryCode', blank=True, null=True)
    share_class_net_assets = models.DecimalField(db_column='ShareClassNetAssets', max_digits=20, decimal_places=0,
                                                 blank=True, null=True)
    share_class_aum = models.DecimalField(db_column='ShareClassAUM', max_digits=20, decimal_places=0, blank=True,
                                          null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Trading'
        unique_together = (('date', 'symbol'),)
        ordering = ('date',)
