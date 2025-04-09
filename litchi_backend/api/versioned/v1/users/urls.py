from django.conf.urls import url, include

from .views import (
    ActivationLogViewSet,
    UserViewSet,
    UserDuplicateViewSet,
    UserConfirmedViewSet,
    UserProfileImageViewSet,
    UserProfileOnwerViewSet,
    UserPasswordChangeViewSet,
    PasswordResetEmailSendViewSet,
    ProfileNicknameDuplicateViewSet,
    UserLoginTokenViewSet,
    TendencyViewSet,
    ValidationEmailSendViewSet,
    VendorTendencyViewSet,
    RefreshTokenViewSet,
)

from .social.urls import urlpatterns as social_urlpatterns

urlpatterns = [
    url(r'^$', UserViewSet.as_view({'post': 'create'})),
    url(r'^profile$',
        UserProfileOnwerViewSet.as_view({'get': 'retrieve', 'put': 'partial_update'})),
    url(r'^profile/avatar$',
        UserProfileImageViewSet.as_view({'post': 'create'})),
    url(r'^profile/nickname/duplicate$',
        ProfileNicknameDuplicateViewSet.as_view({'post': 'duplicate'})),
    url(r'^tendency$',
        TendencyViewSet.as_view({'get': 'retrieve', 'put': 'partial_update'})),
    url(r'^vendors/tendencies$',
        VendorTendencyViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^vendors/tendencies/(?P<pk>[0-9a-f-]+)$',
        VendorTendencyViewSet.as_view({'get': 'retrieve'})),
    url(r'^vendors/tendencies/(?P<pk>[0-9a-f-]+)/submit$',
        VendorTendencyViewSet.as_view({'post': 'submit'})),
    url(r'^(?P<pk>[0-9a-f-]+)$',
        UserViewSet.as_view({'get': 'retrieve', 'put': 'partial_update', 'delete': 'destroy'})),
    url(r'^(?P<pk>[0-9a-f-]+)/password$',
        UserPasswordChangeViewSet.as_view({'put': 'update'})),
    url(r'^login$', UserLoginTokenViewSet.as_view({'post': 'create'})),
    url(r'^logout$', UserViewSet.as_view({'get': 'logout'})),
    url(r'^refresh_token$', RefreshTokenViewSet.as_view({'post': 'partial_update'})),
    url(r'^_health_check$', UserViewSet.as_view({'get': 'health_check'})),
    url(r'^duplicate$', UserDuplicateViewSet.as_view({'post': 'duplicate'})),
    url(r'^activation/(?P<confirm_type>[\w]+)/(?P<activation_key>[\w]+)$',
        ActivationLogViewSet.as_view({'get': 'retrieve'})),
    url(r'^(?P<confirm_type>[\w]+)/activate/(?P<activation_key>[\w]+)$',
        UserConfirmedViewSet.as_view({'get': 'retrieve', 'post': 'create'}), name="email_confirmed"),
    url(r'^password_reset$',
        PasswordResetEmailSendViewSet.as_view({'post': 'create'})),
    url(r'^validate_email$',
        ValidationEmailSendViewSet.as_view({'post': 'create'})),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^social/', include(social_urlpatterns))
]
