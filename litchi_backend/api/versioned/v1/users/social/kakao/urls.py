from django.conf.urls import url
from .views import KakaoLogin

urlpatterns = [
    url(r'^login$', KakaoLogin.as_view())
]
