import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from api.bases.orders.models import Event

logger = logging.getLogger('django.server')


@receiver(post_save, sender=Event)
def update_account_operation_portfolio_id(sender, instance, created, **kwargs):
    if instance.status == Event.STATUS.completed and not instance.completed_at:
        instance.completed_at = timezone.now()
        instance.save(update_fields=['completed_at'])
