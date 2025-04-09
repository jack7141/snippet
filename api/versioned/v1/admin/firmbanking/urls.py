from django.conf.urls import url

from .views import (
    AuthenticationsAdminViewSet,
    AuthAccountAdminViewSet
)

urlpatterns = [
    url(r'^auth$', AuthenticationsAdminViewSet.as_view({'get': 'list'})),
    url(r'^account/(?P<etc_2>[0-9a-f-]+)$', AuthAccountAdminViewSet.as_view({'put': 'partial_update'})),
]