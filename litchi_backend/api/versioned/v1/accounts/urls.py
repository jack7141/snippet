from django.conf.urls import url

from .views import AccountViewSet

urlpatterns = [
    url(r'^(?P<account_alias>[0-9a-zA-Z]+)$', AccountViewSet.as_view({'get': 'retrieve'}))
]
