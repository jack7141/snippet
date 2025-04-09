from django.conf.urls import url
from .views import (
    CalendarViewSet
)

urlpatterns = [
    url(r'^$', CalendarViewSet.as_view({'get': 'list'})),
    url(r'(?P<pk>[0-9-]+)/holiday_interval/(?P<days>[0-9]+)$', CalendarViewSet.as_view({'get': 'holiday_interval'})),
    url(r'(?P<pk>[0-9-]+)$', CalendarViewSet.as_view({'get': 'retrieve'})),
]
