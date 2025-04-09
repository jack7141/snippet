from django.conf.urls import url
from .views import (
    SMSCertViewSet,
    AccountCertViewSet,
    OwnerCertViewSet,
    ARSCertViewSet,
    AuthAccountViewSet
)

urlpatterns = [
    url(r'^ars$', ARSCertViewSet.as_view({'post': 'create', 'get': 'validation'})),
    url(r'^sms$', SMSCertViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^sms/validate$', SMSCertViewSet.as_view({'post': 'validate'})),
    url(r'^accounts$', AccountCertViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^accounts/validate$', AccountCertViewSet.as_view({'post': 'validate'})),
    url(r'^accounts/real_name$', AccountCertViewSet.as_view({'post': 'real_name'})),
    url(r'^accounts/(?P<etc_2>[0-9a-f-]+)/last$', AuthAccountViewSet.as_view({'get': 'retrieve'})),
    url(r'^owner$', OwnerCertViewSet.as_view({'post': 'create'})),
]
