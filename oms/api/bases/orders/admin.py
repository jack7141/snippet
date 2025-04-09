# Register your models here.
from django.contrib import admin

from .models import Event, OrderDetail, OrderSetting


@admin.register(Event)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("account_alias", "status", "mode", "created_at", "completed_at")
    list_filter = ("status", "mode")
    search_fields = ("account_alias__account_alias",)


@admin.register(OrderDetail)
class OrderDetailAdmin(admin.ModelAdmin):
    list_display = (
        "account_alias",
        "code",
        "type",
        "shares",
        "order_price",
        "paid_price",
        "order_price_usd",
        "paid_price_usd",
        "result",
        "ordered_at",
        "paid_at",
    )
    list_filter = ("ordered_at", "paid_at")
    search_fields = ("account_alias__account_alias", "code")


@admin.register(OrderSetting)
class OrderSettings(admin.ModelAdmin):
    list_display = ["id", "name", "min_base", "emphasis", "strategies"]
