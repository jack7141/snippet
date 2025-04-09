from django.conf import settings
from django.conf.urls import url
from rest_framework import routers
from api.versioned.v1.admin.contracts.views import (
    ConditionAdminViewSet,
    ContractUserAdminViewSet,
    ContractAdminViewSet,
    ContractFilterAdminViewSet,
    ContractDeletionAdminViewSet,
    ContractDashboardViewSet,
    ContractNextStepViewSet,
    DProgSyncViewSet,
    ExtraAdminViewSet,
    ProvisionalAdminViewSet,
    RebalancingQueueAdminViewSet,
    TermAdminViewSet,
    TransferAdminViewSet
)

router = routers.SimpleRouter(trailing_slash=False)
router.register(r'terms', TermAdminViewSet)
urlpatterns = router.urls

urlpatterns += [
    url(r'^$', ContractFilterAdminViewSet.as_view({'post': 'create', 'get': 'list'})),
    url(r'^issuance$', ContractFilterAdminViewSet.as_view({'get': 'issue_context_list'})),
    url(r'^simple$', ContractFilterAdminViewSet.as_view({'get': 'simple_list'})),
    url(r'^condition/(?P<pk>[0-9a-f-]+)$', ConditionAdminViewSet.as_view({'put': 'partial_update'})),
    url(r'^extra/(?P<pk>[0-9a-f-]+)$', ExtraAdminViewSet.as_view({'put': 'partial_update'})),
    url(r'^deletion$', ContractDeletionAdminViewSet.as_view({'get': 'list', 'delete': 'destroy'})),
    url(r'^clean$', ContractDeletionAdminViewSet.as_view({'get': 'list', 'delete': 'clean'})),
    url(r'^users$', ContractUserAdminViewSet.as_view({'get': 'list'})),
    url(r'^dashboard$', ContractDashboardViewSet.as_view({'get': 'retrieve'})),
    url(r'^sync$', DProgSyncViewSet.as_view({'post': 'create'})),
    url(r'^transfer$', TransferAdminViewSet.as_view({'get': 'list'})),
    url(r'^transfer/(?P<pk>[0-9a-f-]+)$', TransferAdminViewSet.as_view({'put': 'partial_update'})),
    url(r'^(?P<pk>[0-9a-f-]+)$', ContractAdminViewSet.as_view({'get': 'retrieve', 'delete': 'destroy',
                                                               'put': 'partial_update'})),
    url(r'provisional$', ProvisionalAdminViewSet.as_view({'get': 'list'})),
    url(r'provisional/(?P<pk>[0-9a-f-]+)$', ProvisionalAdminViewSet.as_view({'get': 'retrieve'})),
    url(r'^rebalancing/queue/$', RebalancingQueueAdminViewSet.as_view({'post': 'create', 'get': 'list'})),
    url(r'^rebalancing/queue/batch$', RebalancingQueueAdminViewSet.as_view({'patch': 'batch'})),
    url(r'^rebalancing/queue/(?P<contract_id>[0-9a-f-]+)$', RebalancingQueueAdminViewSet.as_view(
        {'patch': 'do_rebalancing', 'delete': 'destroy'}))
]

if settings.DEBUG:
    urlpatterns += [url(r'next/(?P<pk>[0-9a-f-]+)$', ContractNextStepViewSet.as_view({'post': 'create'}))]
