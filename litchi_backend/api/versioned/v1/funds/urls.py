from django.conf.urls import url
from .views import (
    OperationListViewSet,
    OperationRetrieveViewSet,
    TradingViewSet
)

urlpatterns = [
    url(r'^$', OperationListViewSet.as_view({'get': 'list'})),
    url(r'^(?P<symbol>[\w-]+)$', OperationRetrieveViewSet.as_view({'get': 'retrieve'})),
    url(r'^(?P<symbol>[\w-]+)/trading$', TradingViewSet.as_view({'get': 'list'})),
]
