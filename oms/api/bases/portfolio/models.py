from django.db import models
from common.models import ListField
from common.decorators import cached_property


class Portfolio(models.Model):
    port_seq = models.BigIntegerField(primary_key=True)
    port_date = models.DateField()
    port_type = models.IntegerField()
    port_data = ListField()
    bw_type = models.IntegerField()
    update_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "bluewhale_portfolio"
        ordering = ("-port_date",)

    @cached_property
    def universe_index(self):
        return int(str(self.port_seq)[8:12])

    @cached_property
    def symbols(self):
        return [
            item.get("code")
            for item in self.port_data
            if item.get("code") != "000000000000"
        ]
