from django.conf.urls import url
from .views import (
    NotificationViewSet,
    SubscribeViewSet,
    NonAuthSubscribeViewSet,
    DeviceViewSet,
    TopicViewSet
)
from common.routers import CustomSimpleRouter

router = CustomSimpleRouter(trailing_slash=False)
router.register(r'subscribes', SubscribeViewSet)

urlpatterns = router.urls + [
    url(r'^$', NotificationViewSet.as_view({'get': 'list'})),
    url(r'^devices$', DeviceViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^devices/(?P<pk>[0-9a-f-]+)$', DeviceViewSet.as_view({'delete': 'destroy'})),
    url(r'^subscribes/(?P<type_name>[0-9a-zA-Z]+)/(?P<topic_name>[a-zA-Z]+)$',
        NonAuthSubscribeViewSet.as_view({'put': 'update', 'delete': 'destroy'})),
    url(r'^topics$', TopicViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^topics/(?P<pk>[0-9a-f-]+)$', TopicViewSet.as_view({'delete': 'destroy'})),
]
