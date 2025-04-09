from django.conf.urls import url
from .views import (
    AdminOrderViewSet,
    AdminRebalancingViewSet,
    AdminOrderBulkViewSet,
    AdminRebalancingNotifyViewSet,
    AdminReservedActionViewSet
)

urlpatterns = [
    url(r'^$', AdminOrderViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^bulk$', AdminOrderBulkViewSet.as_view({'post': 'create'})),
    url(r'^rebalancing$', AdminRebalancingViewSet.as_view({'get': 'list'})),
    url(r'^rebalancing/check$', AdminRebalancingViewSet.as_view({'post': 'create'})),
    url(r'^rebalancing/notify$', AdminRebalancingNotifyViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^rebalancing/reserved$', AdminReservedActionViewSet.as_view({'post': 'create'})),
    url(r'^rebalancing/contracts/(?P<pk>[0-9a-f-]+)$', AdminRebalancingViewSet.as_view({'post': 'contract'}))
]
