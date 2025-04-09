# Register your models here.
from django.contrib import admin

from .models import (
    Event, OrderDetail, OrderSetting
)


@admin.register(Event)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'account_alias', 'portfolio_id', 'status', 'mode', 'created_at', 'completed_at'
    )
    list_filter = ('status', 'mode')
    search_fields = ('account_alias__account_alias',)
    readonly_fields = ('account_alias', 'portfolio_id', 'mode', 'completed_at')


@admin.register(OrderDetail)
class OrderDetailAdmin(admin.ModelAdmin):
    list_display = (
        'account_alias',
        'code', 'type', 'shares',
        'order_price', 'paid_price',
        'order_price_usd', 'paid_price_usd',
        'result',
        'ordered_at', 'paid_at'
    )
    list_filter = ('ordered_at', 'paid_at')
    search_fields = ('account_alias__account_alias', 'code')


@admin.register(OrderSetting)
class OrderSettings(admin.ModelAdmin):
    list_display = ['id', 'name', 'emphasis', 'strategies']
