from django.urls import path
from .views import StatusViewSet

urlpatterns = [
    # Account 서버 정상 작동 check
    path(r"health-check", StatusViewSet.as_view({"get": "status"}), name="status"),
]
