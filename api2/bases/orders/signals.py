import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from api.bases.orders.models import Event

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Event)
def update_account_operation_portfolio_id(sender, instance, created, **kwargs):
    # account_alias.portfolio_field deleted. No need to be updated.
    # if created \
    #         and instance.portfolio_id is not None \
    #         and instance.status in [Event.STATUS.on_hold]:
    #     account_alias = instance.account_alias
    #     account_alias.risk_typ3 = instance.portfolio_id[]
    #     account_alias.save(update_fields=['portfolio_id'])

    if instance.status == Event.STATUS.completed and not instance.completed_at:
        instance.completed_at = timezone.now()
        instance.save(update_fields=["completed_at"])
