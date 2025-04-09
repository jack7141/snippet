from allauth.socialaccount.providers.naver.provider import NaverProvider as allauth_NaverProvider
from common.providers.base import ProviderMixin


class NaverProvider(ProviderMixin, allauth_NaverProvider):
    pass


provider_classes = [NaverProvider]
