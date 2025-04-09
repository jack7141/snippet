from django.conf.urls import url
from .views import (
    OrderViewSet,
    OrderBasketViewSet,
    OrderDetailViewSet
)

urlpatterns = [
    url(r'^$', OrderViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^details$', OrderDetailViewSet.as_view({'get': 'list'})),
    url(r'^(?P<order_item>[0-9a-f-]+)/basket$', OrderBasketViewSet.as_view({'get': 'retrieve'})),
]
