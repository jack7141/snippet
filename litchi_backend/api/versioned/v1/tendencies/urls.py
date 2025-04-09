from django.conf.urls import url
from common.routers import CustomSimpleRouter
from .views import (
    TypeViewSet,
    ResponseViewSet,
    ReasonViewSet,
)

router = CustomSimpleRouter()

urlpatterns = router.urls + [
    url(r'^types$', TypeViewSet.as_view({'get': 'list'})),
    url(r'^types/(?P<code>\w+)$', TypeViewSet.as_view({'get': 'retrieve'})),
    url(r'^responses$', ResponseViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^reasons$', ReasonViewSet.as_view({'get': 'list'})),
]
