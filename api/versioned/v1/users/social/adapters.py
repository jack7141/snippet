from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.sites.shortcuts import get_current_site


class FountSocialAccountAdapter(DefaultSocialAccountAdapter):

    def new_user(self, request, sociallogin):
        user = super().new_user(request, sociallogin)
        user.site = get_current_site(request)
        return user

    def save_user(self, request, sociallogin, form=None):
        u = super().save_user(request, sociallogin, form)

        if request.method == 'POST' and request.POST.get('invite'):
            invite = request.POST.get('invite')
            inviter_id = invite.pop('inviter')
            obj = dict({'inviter_id': inviter_id}, **invite)
            u.invites.model.objects.create(**dict({'joiner': u}, **obj))
        return u
