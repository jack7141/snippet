from django.conf.urls import url
from .views import (
    VendorContractViewSet,
    VendorContractUserViewSet,
    VendorOrderViewSet,
    VendorTokenViewSet,
    ExchangeRateViewSet
)

urlpatterns = [
    url(r'^contracts/users$', VendorContractUserViewSet.as_view({'get': 'list'})),
    url(r'^contracts/(?P<pk>[0-9a-f-]+)$', VendorContractViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'})),
    url(r'^orders$', VendorOrderViewSet.as_view({'post': 'create'})),
    url(r'^(?P<vendor_code>\w+)/token$', VendorTokenViewSet.as_view({'get': 'retrieve'})),
    url(r'^exchange_rate$', ExchangeRateViewSet.as_view({'get': 'retrieve'})),
]
