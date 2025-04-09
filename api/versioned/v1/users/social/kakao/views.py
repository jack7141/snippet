import requests

from rest_framework.status import is_success
from rest_framework.exceptions import ValidationError

from allauth.socialaccount.providers.kakao.views import KakaoOAuth2Adapter
from rest_auth.registration.views import SocialLoginView
from api.versioned.v1.users.social.serializers import SocialLoginSerializer


class FountKakaoOAuth2Adapter(KakaoOAuth2Adapter):
    def complete_login(self, request, app, token, **kwargs):
        headers = {'Authorization': 'Bearer {0}'.format(token.token)}
        resp = requests.get(self.profile_url, headers=headers)

        if not is_success(resp.status_code):
            raise ValidationError(detail=resp.json())

        extra_data = resp.json()

        if not extra_data.get('kakao_account').get('is_email_valid'):
            raise ValidationError(detail='email not valid')

        return self.get_provider().sociallogin_from_response(request,
                                                             extra_data)


class KakaoLogin(SocialLoginView):
    adapter_class = FountKakaoOAuth2Adapter
    serializer_class = SocialLoginSerializer
