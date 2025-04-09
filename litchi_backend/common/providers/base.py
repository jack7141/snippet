from allauth.socialaccount.adapter import get_adapter
from django.contrib.sites.shortcuts import get_current_site


class ProviderMixin:
    def sociallogin_from_response(self, request, response):
        from allauth.socialaccount.models import SocialLogin, SocialAccount

        adapter = get_adapter(request)
        site = get_current_site(request)
        uid = f'{self.extract_uid(response)}-{site.id}'
        extra_data = self.extract_extra_data(response)
        common_fields = self.extract_common_fields(response)
        socialaccount = SocialAccount(extra_data=extra_data,
                                      uid=uid,
                                      provider=self.id)
        email_addresses = self.extract_email_addresses(response)
        self.cleanup_email_addresses(common_fields.get('email'),
                                     email_addresses)
        sociallogin = SocialLogin(account=socialaccount,
                                  email_addresses=email_addresses)
        user = sociallogin.user = adapter.new_user(request, sociallogin)
        user.set_unusable_password()
        adapter.populate_user(request, sociallogin, common_fields)
        return sociallogin
