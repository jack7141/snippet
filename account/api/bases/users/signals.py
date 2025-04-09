from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out

from .models import User, Profile
from common.decorators import disable_for_loaddata


@receiver(post_save, sender=User)
@disable_for_loaddata
def create_user_info(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def online_user_logged_in(sender, request, user, **kwargs):
    user.is_online = True
    user.save()


@receiver(user_logged_out)
def offline_user_logged_out(sender, request, user, **kwargs):
    user.is_online = False
    user.save()
    try:
        user.auth_token.delete()
    except:
        pass
