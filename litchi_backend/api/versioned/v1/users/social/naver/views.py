import requests

from rest_framework.status import is_success
from rest_framework.exceptions import ValidationError

from allauth.socialaccount.providers.naver.views import NaverOAuth2Adapter
from rest_auth.registration.views import SocialLoginView
from api.versioned.v1.users.social.serializers import SocialLoginSerializer


class FountNaverOAuth2Adapter(NaverOAuth2Adapter):
    def complete_login(self, request, app, token, **kwargs):
        headers = {'Authorization': 'Bearer {0}'.format(token.token)}
        resp = requests.get(self.profile_url, headers=headers)

        if not is_success(resp.status_code):
            raise ValidationError(detail=resp.json())

        extra_data = resp.json().get('response')
        return self.get_provider().sociallogin_from_response(request,
                                                             extra_data)


class NaverLogin(SocialLoginView):
    adapter_class = FountNaverOAuth2Adapter
    serializer_class = SocialLoginSerializer
