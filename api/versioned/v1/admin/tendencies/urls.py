from django.conf.urls import url
from api.versioned.v1.admin.tendencies.views import (
    ResponseAdminViewSet
)

urlpatterns = [
    url(r'^responses/latest$', ResponseAdminViewSet.as_view({'get': 'list'})),
]
