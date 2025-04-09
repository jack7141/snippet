from django.contrib import admin
from api.bases.reports.models import (
    ManagementReportHeader, ManagementReport,
    TradingDetail, ManagerDetail, HoldingDetail, RoboAdvisorDesc, AssetUniverse, Performance
)
# Register your models here.


@admin.register(ManagementReportHeader)
class ManagementReportHeaderAdmin(admin.ModelAdmin):
    list_display = ('year', 'quarter', 'strategy_code', 'strategy', 'created_at', 'updated_at')


@admin.register(ManagementReport)
class ManagementReportAdmin(admin.ModelAdmin):
    list_display = ('year', 'quarter', 'strategy_code', 'account_alias_id',
                    'port_risk_type', 'baseline_date',
                    'is_published')
    list_filter = ('year', 'quarter', 'strategy_code', 'is_published')


@admin.register(TradingDetail)
class TradeAdmin(admin.ModelAdmin):
    list_display = ('year', 'quarter', 'account_alias_id', 'trade_type', 'asset_name',
                    'trade_date', 'created_at', 'updated_at')
    list_filter = ('year', 'quarter', 'trade_type', 'created_at', 'updated_at')


@admin.register(ManagerDetail)
class ManagerDetailAdmin(admin.ModelAdmin):
    list_display = ('year', 'quarter', 'strategy_code', 'name', 'is_certified')
    list_filter = ('year', 'quarter', 'strategy_code', 'created_at', 'updated_at')


@admin.register(HoldingDetail)
class HoldingAdmin(admin.ModelAdmin):
    list_display = ('year', 'quarter', 'account_alias_id', 'code', 'asset_name', 'shares',
                    'acquisition_price', 'market_price', 'created_at', 'updated_at')
    list_filter = ('year', 'quarter', 'created_at', 'updated_at')


@admin.register(RoboAdvisorDesc)
class RoboAdvisorDescAdmin(admin.ModelAdmin):
    list_display = ('year', 'quarter', 'algorithm_name', 'strategy_code',
                    'created_at', 'updated_at')
    list_filter = ('year', 'quarter', 'strategy_code', 'created_at', 'updated_at')


@admin.register(AssetUniverse)
class AssetUniverseAdmin(admin.ModelAdmin):
    list_display = (
        'year', 'quarter', 'code', 'asset_name', 'created_at', 'updated_at'
    )
    list_filter = ('year', 'quarter', 'created_at', 'updated_at')


@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
    list_display = (
        'year', 'quarter', 'account_alias_id', 'base_amount', 'evaluation_amount', 'acc_return', 'period_return',
        'from_date', 'to_date', 'effective_date'
    )
    list_filter = ('year', 'quarter')
