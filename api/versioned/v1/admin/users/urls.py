from django.conf.urls import url
from api.versioned.v1.admin.users.views import (
    TokenAdminViewSet,
    UserAdminViewSet,
    UserProfileAdminViewSet
)

urlpatterns = [
    url(r'^$', UserAdminViewSet.as_view({'get': 'list'})),
    url(r'^(?P<pk>[0-9a-f-]+)$', UserAdminViewSet.as_view({'put': 'partial_update', 'get': 'retrieve'})),
    url(r'^profile/(?P<pk>[0-9a-f-]+)$',
        UserProfileAdminViewSet.as_view({'get': 'retrieve', 'put': 'partial_update'})),
    url(r'^expired/(?P<pk>[0-9a-f-]+)$', TokenAdminViewSet.as_view({'get': 'expired'})),
]
