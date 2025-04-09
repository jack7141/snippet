from api.bases.accounts.models import Account
from reversion.models import Version
from django.db.models.signals import pre_delete
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=Account, dispatch_uid="account_delete_signal")
def delete_reversion(sender, instance: Account, **kwargs):
    try:
        _version_queryset = Version.objects.select_related("revision").get_for_object(
            instance
        )
        for _version in _version_queryset:
            _version.revision.delete()
        _version_queryset.delete()
    except Exception as e:
        logger.warning(f"{instance} versions are failed to delete: {str(e)}")
