from allauth.socialaccount.providers.kakao.provider import KakaoProvider as allauth_KakaoProvider
from common.providers.base import ProviderMixin


class KakaoProvider(ProviderMixin, allauth_KakaoProvider):
    pass


provider_classes = [KakaoProvider]
