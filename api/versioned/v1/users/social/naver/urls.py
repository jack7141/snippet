from django.conf.urls import url
from .views import NaverLogin

urlpatterns = [
    url(r'^login$', NaverLogin.as_view())
]
