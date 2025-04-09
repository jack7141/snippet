from django.conf.urls import url
from .views import StatusViewSet

urlpatterns = [
    url(r'^health-check$', StatusViewSet.as_view({'get': 'status'}))
]