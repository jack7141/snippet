from django.conf.urls import url
from django.urls import path
from django.urls import register_converter

from common.routers import CustomSimpleRouter
from common.url_patterns import YearMonthDayConverter
from .views import (
    AccountViewSet, AccountCleanUpViewSet,
    AssetViewSet, AssetDetailViewSet, AccountDumpViewSet,
    AmountViewSet,
    AccountExecutionViewSet,
    AccountTradeViewSet, AccountTradeAmountViewSet, AccountTradeSumUpViewSet,
    SettlementViewSet, HoldingViewSet, DailyBalanceViewSet,
    AccountAssetViewSet, SuspensionAccountViewSet, PensionViewSet
)

router = CustomSimpleRouter(trailing_slash=False)
router.register(r'assets/details', AssetDetailViewSet)
router.register(r'assets', AssetViewSet)
router.register(r'amounts', AmountViewSet)
router.register(r'trades', AccountTradeViewSet)
router.register(r'executions', AccountExecutionViewSet)
router.register(r'sum-up', AccountTradeSumUpViewSet)
router.register(r'settlement', SettlementViewSet),
router.register(r'holdings', HoldingViewSet)
router.register(r'balance', DailyBalanceViewSet)
router.register(r'abnormal', SuspensionAccountViewSet)
router.register(r'pension/diff', PensionViewSet)
router.register(r'', AccountViewSet)

register_converter(YearMonthDayConverter, 'yyyymmdd')

urlpatterns = [
    url(r'cleanup', AccountCleanUpViewSet.as_view({'get': 'list', 'delete': 'destroy'})),
    path(r'dump', AccountDumpViewSet.as_view({'get': 'dump'})),
    path(r'dump/assets/', AccountDumpViewSet.as_view({'get': 'dump_assets'})),
    path(r'dump/pension', AccountDumpViewSet.as_view({'get': 'dump_pension'})),
    path(r'amounts/queue', AmountViewSet.as_view({'post': 'create_queue'})),
    path(r'amounts/queue/<task_id>', AmountViewSet.as_view({'get': 'get_queue_state'})),
    path(r'amounts/check/<account_alias>', AmountViewSet.as_view({'get': 'check_amount'})),
    path(r'sum-up/names', AccountTradeSumUpViewSet.as_view({'get': 'get_j_names'})),
    path(r'sum-up/groups/amount-types', AccountTradeSumUpViewSet.as_view({'get': 'get_amount_func_types'})),
    path(r'sum-up/groups/trade-types', AccountTradeSumUpViewSet.as_view({'get': 'get_trade_types'})),
    path(r'trades/amount/<account_alias>', AccountTradeAmountViewSet.as_view({'get': "calc_amount"})),
    path(r'asset/<account_alias_id>', AccountAssetViewSet.as_view({'put': "calc_asset"})),
    path(r'asset/quarter/', AssetViewSet.as_view({'get': "calc_quarter"})),
]

urlpatterns += router.urls
