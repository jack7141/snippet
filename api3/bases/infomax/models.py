from django.db import models

from .managers import ClosingPriceQuerySet


class Bid(models.Model):
    trcd = models.CharField(max_length=2, blank=True, null=True)
    symbol = models.CharField(max_length=16, blank=True, null=True)
    loc_date = models.DateField(blank=True, null=True)
    loc_time = models.TimeField(blank=True, null=True)
    kor_date = models.DateField(blank=True, null=True)
    kor_time = models.TimeField(blank=True, null=True)
    tot_bid_size = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    tot_ask_size = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    tot_bid_count = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    tot_ask_count = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    nrec = models.SmallIntegerField(blank=True, null=True)
    bid = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    ask = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    bid_size = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    ask_size = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    bid_count = models.DecimalField(max_digits=6, decimal_places=0, blank=True, null=True)
    ask_count = models.DecimalField(max_digits=6, decimal_places=0, blank=True, null=True)
    timestamp = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'bid'


class ClosingPrice(models.Model):
    objects = ClosingPriceQuerySet.as_manager()

    trcd = models.CharField(max_length=2, blank=True, null=True)
    symbol = models.CharField(max_length=16, blank=True, null=True)
    busi_date = models.DateField(blank=True, null=True)
    open = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    high = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    low = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    last = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    sign = models.SmallIntegerField(blank=True, null=True)
    diff = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    bid = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    bid_size = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    ask = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    ask_size = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    volume = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    amount = models.DecimalField(max_digits=14, decimal_places=0, blank=True, null=True)
    timestamp = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'closing_price'
        unique_together = (('busi_date', 'symbol'),)

    def __str__(self):
        return f"ClosingPrice({self.busi_date}|{self.symbol}|{self.last}|{self.timestamp})"


class Master(models.Model):
    trcd = models.CharField(max_length=2, blank=True, null=True)
    symbol = models.CharField(max_length=16, blank=True, null=True)
    kor_name = models.CharField(max_length=64, blank=True, null=True)
    eng_name = models.CharField(max_length=64, blank=True, null=True)
    nation_code = models.CharField(max_length=2, blank=True, null=True)
    currency_code = models.CharField(max_length=4, blank=True, null=True)
    isin = models.CharField(max_length=12, blank=True, null=True)
    float_point = models.SmallIntegerField(blank=True, null=True)
    instrument = models.SmallIntegerField(blank=True, null=True)
    industry = models.CharField(max_length=4, blank=True, null=True)
    share = models.BigIntegerField(blank=True, null=True)
    market_cap = models.BigIntegerField(blank=True, null=True)
    par = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    par_currency = models.CharField(max_length=4, blank=True, null=True)
    perv = models.DecimalField(max_digits=13, decimal_places=4, blank=True, null=True)
    epsv = models.DecimalField(max_digits=13, decimal_places=4, blank=True, null=True)
    epsd = models.DateField(blank=True, null=True)
    bid_lot_size = models.IntegerField(blank=True, null=True)
    ask_lot_size = models.IntegerField(blank=True, null=True)
    adj_close = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    up_limit = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    down_limit = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    high52p = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    high52d = models.DateField(blank=True, null=True)
    low52p = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    low52d = models.DateField(blank=True, null=True)
    listed_date = models.DateField(blank=True, null=True)
    expire_date = models.DateField(blank=True, null=True)
    suspend = models.CharField(max_length=1, blank=True, null=True)
    base_date = models.DateField(blank=True, null=True)
    tick_type = models.IntegerField(blank=True, null=True)
    prev_close = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    prev_volume = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    hyrp = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    hyrd = models.DateField(blank=True, null=True)
    lyrp = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    lyrd = models.DateField(blank=True, null=True)
    timestamp = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'master'
        unique_together = (('base_date', 'symbol'),)


class Quote(models.Model):
    trcd = models.CharField(max_length=2, blank=True, null=True)
    symbol = models.CharField(max_length=16, blank=True, null=True)
    busi_date = models.DateField(blank=True, null=True)
    loc_date = models.DateField(blank=True, null=True)
    loc_time = models.TimeField(blank=True, null=True)
    kor_date = models.DateField(blank=True, null=True)
    kor_time = models.TimeField(blank=True, null=True)
    open = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    high = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    low = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    last = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    sign = models.SmallIntegerField(blank=True, null=True)
    diff = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    bid = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    bid_size = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    ask = models.DecimalField(max_digits=16, decimal_places=4, blank=True, null=True)
    ask_size = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    exec_volume = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    volume = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    amount = models.DecimalField(max_digits=14, decimal_places=0, blank=True, null=True)
    session = models.SmallIntegerField(blank=True, null=True)
    qtyp = models.SmallIntegerField(blank=True, null=True)
    timestamp = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'quote'
