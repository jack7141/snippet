# Register your models here.
from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import ExchangeRate


@admin.register(ExchangeRate)
class ExchangeRateAdmin(VersionAdmin):
    list_display = ('currency_code', 'base_date', 'open', 'close', 'high', 'low', 'created_at', 'updated_at')
    list_filter = ('currency_code', 'base_date')
