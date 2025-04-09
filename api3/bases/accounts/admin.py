# Register your models here.
from django.contrib import admin
from django_admin_inline_paginator.admin import TabularInlinePaginated
from reversion.admin import VersionAdmin

from api.bases.orders.models import Event
from .models import (
    Account, Asset, AssetDetail, AmountHistory,
    Execution, Trade,
    Holding, Settlement, SumUp
)


class AccountNumberSearchMixin(object):
    search_fields = ('account_alias__in',)

    def get_account_pk(self, search_term):
        accounts = []
        for item in Account.objects.iterator():
            if str(search_term) in str(item.account_number):
                accounts.append(str(item.pk))

        return accounts

    def get_search_results(self, request, queryset, search_term):
        search_fields = self.get_search_fields(request)
        if not search_term:
            return queryset, False

        account_alias = queryset.filter(account_alias=search_term)

        if account_alias.exists():
            return account_alias, False

        accounts = self.get_account_pk(search_term)
        for field in search_fields:
            queryset = queryset.filter(**{field: accounts})
        return queryset, False


class AssetTabularInline(TabularInlinePaginated):
    model = Asset
    ordering = ['-created_at']
    can_delete = False
    extra = 0
    readonly_fields = ['base', 'eval_amt', 'profit_loss', 'deposit', 'balance', 'prev_deposit',
                       'base_usd', 'deposit_usd', 'balance_usd', 'created_at']
    per_page = 10

class EventTabularInline(TabularInlinePaginated):
    model = Event
    ordering = ['-created_at']
    can_delete = False
    extra = 0
    readonly_fields = ['portfolio_id', 'mode', 'status', 'created_at', 'completed_at']
    per_page = 10


@admin.register(Account)
class AccountAdmin(AccountNumberSearchMixin, VersionAdmin):
    list_display = ('account_number', 'type', 'vendor_code', 'account_type', 'status', 'risk_type', 'strategy_code',
                    'created_at', 'updated_at', 'deleted_at')
    list_filter = (
                    'type', 'vendor_code', 'account_type', 'status', 'risk_type', 'strategy_code',
                    'created_at', 'updated_at', 'deleted_at')
    readonly_fields = ('account_number', 'type', 'pension_base_diff', 'vendor_code', 'order_setting', 'strategy_code',
                       'risk_type', 'account_type', 'account_alias')
    inlines = [EventTabularInline, AssetTabularInline]
    history_latest_first = True

    def reversion_register(self, model, **options):
        options['exclude'] = ('account_number',)
        super().reversion_register(model, **options)


class AssetAdmin(AccountNumberSearchMixin, admin.ModelAdmin):
    list_display = ('account_alias',
                    'base', 'deposit', 'balance', 'prev_deposit',
                    'base_usd', 'deposit_usd', 'balance_usd',
                    'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')


class AssetDetailAdmin(AccountNumberSearchMixin, admin.ModelAdmin):
    list_display = ('account_alias',
                    'code', 'shares',
                    'buy_price', 'balance',
                    'buy_price_usd', 'balance_usd',
                    'created_at', 'updated_at')
    list_filter = ('code', 'created_at', 'updated_at',)


@admin.register(AmountHistory)
class AmountHistoryAdmin(admin.ModelAdmin):
    list_display = (
        'account_alias',
        'input_amt', 'output_amt', 'import_amt', 'export_amt',
        'oversea_tax_amt', 'oversea_tax_refund_amt',
        'created_at', 'updated_at'
    )


@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    list_display = (
        'account_alias', 'order_date', 'ord_no', 'code', 'code_name', 'trade_sec_name',
        'order_status', 'exec_qty', 'exec_price',
        'ord_qty', 'ord_price', 'unexec_qty', 'org_ord_no', 'mkt_clsf_nm',
        'currency_code', 'ord_sec_name', 'aplc_excj_rate', 'reject_reason', 'ex_code',
        'exchange_rate', 'org_price',
        'created_at', 'updated_at'
    )
    list_filter = ('trade_sec_name', 'order_tool_name', 'created_at', 'updated_at')
    search_fields = ('account_alias__account_alias',)


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = (
        'account_alias', 'trd_date', 'ord_no', 'quantity',
        'deposit_amt', 'commission', 'in_come_tax', 'currency_name',
        'pre_p_deposit', 'ex_deposit', 'j_name', 'j_code',
        'trd_p', 'trd_tax',
        'reside_tax', 'perfor_qty', 'ex_chg_rate', 'pre_pay_repay',
        'stock_name', 'trd_amt', 'agr_tax', 'unpaid_repay',
        'etc_repay', 'stock_qtry', 'for_comm_r', 'for_amt_r', 'st_stock_code', 'for_amt',
        'created_at', 'updated_at'
    )
    list_filter = ('created_at', 'updated_at', 'j_name')
    search_fields = ('account_alias__account_alias', 'j_code')


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = (
        'account_alias',
        'base',
        'input_amt', 'output_amt', 'import_amt', 'export_amt',
        'dividend_input_amt', 'dividend',
        'deposit', 'for_deposit',
        'settled_for_amt', 'settled_for_bid_amt', 'settled_for_ask_amt',
        'commission', 'in_come_tax', 'reside_tax',
        'for_trd_tax', 'for_commission',
        'created_at', 'updated_at'
    )
    list_filter = ('created_at', 'updated_at')
    search_fields = ('account_alias',)


@admin.register(SumUp)
class SumUpAdmin(admin.ModelAdmin):
    list_display = (
        'j_name', 'j_code', 'trade_type', 'amount_func_type', 'managed', 'description',
        'created_at', 'updated_at'
    )
    list_filter = ('managed', 'trade_type', 'amount_func_type', 'created_at', 'updated_at')


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ('account_alias', 'code', 'shares', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')


admin.site.register(Asset, AssetAdmin)
admin.site.register(AssetDetail, AssetDetailAdmin)
