from django.conf.urls import url
from .views import (
    NotificationViewSet
)

urlpatterns = [
    url(r'^$', NotificationViewSet.as_view({'get': 'list', 'post': 'create'}))
]
