from django.db import models
from common.asset_enums import ASSET_CODES


class MarketIndex(models.Model):
    date = models.DateField(db_column='AsOfDate', primary_key=True)
    symbol = models.CharField(db_column='Symbol', max_length=32)
    name = models.CharField(db_column='IndexName', max_length=128)
    price = models.DecimalField(db_column='Price', max_digits=24, decimal_places=10, blank=True, null=True)
    update_date = models.DateTimeField(db_column='UpdateDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'MarketIndex'
        unique_together = (('date', 'symbol'),)


class Profile(models.Model):
    perm_id = models.CharField(db_column='PermID', primary_key=True, max_length=20)
    isin = models.CharField(db_column='ISIN', max_length=12)
    symbol = models.CharField(db_column='Symbol', max_length=10, blank=True, null=True)
    name = models.CharField(db_column='AssetName', max_length=128, blank=True, null=True)
    asset_class = models.CharField(db_column='AssetClass', max_length=64, blank=True, null=True)
    asset_niche = models.CharField(db_column='AssetNiche', max_length=64, blank=True, null=True)
    specific_geography = models.CharField(db_column='SpecificGeography', max_length=64, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Profile'

    def get_asset_category(self):
        if self.asset_class == 'Equity':
            return ASSET_CODES.stock
        elif self.asset_class == 'Fixed Income':
            return ASSET_CODES.bond
        elif self.asset_class == 'Commodities':
            return ASSET_CODES.commodity
        elif self.asset_class == 'Alternatives':
            return ASSET_CODES.alternative
        else:
            return ASSET_CODES.etc
