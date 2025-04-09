from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Notification, Subscribe, Topic
from .choices import NotificationChoices

from common.decorators import disable_for_loaddata


@receiver(post_save, sender=Notification)
@disable_for_loaddata
def send_transition(sender, instance, created, **kwargs):
    if created:
        instance.send_notification()


@receiver(post_save, sender=get_user_model())
@disable_for_loaddata
def add_subscribe(sender, instance, created, **kwargs):
    if created:
        topic = Topic.objects.get(name='notification')
        for protocol in [NotificationChoices.PROTOCOLS.sms,
                         NotificationChoices.PROTOCOLS.email,
                         NotificationChoices.PROTOCOLS.push,
                         NotificationChoices.PROTOCOLS.app]:
            sub_instance, _ = Subscribe.objects.get_or_create(
                user=instance,
                type=protocol
            )
            sub_instance.topics.add(topic)
