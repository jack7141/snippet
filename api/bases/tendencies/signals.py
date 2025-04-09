import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from api.bases.notifications.models import Notification, Topic
from api.bases.notifications.choices import NotificationChoices

from api.bases.tendencies.contexts import ResponseContext
from api.bases.tendencies.models import Response

from common.decorators import disable_for_loaddata, skip_signal
from common.contexts import MessageContextFactory, NotiTopic, NotiStatus, NotiStep, ProductCode

logger = logging.getLogger('django.server')


@receiver(pre_save, sender=Response)
@disable_for_loaddata
def skip_messages(sender, instance, **kwargs):
    try:
        response = instance.user.profile.last_tendency_response
        if response.risk_type is not None and not int(response.risk_type):
            instance.skip_signal = True
    except Response.DoesNotExist:
        pass


@receiver(post_save, sender=Response)
@disable_for_loaddata
@skip_signal()
def send_transition(sender, instance, created, **kwargs):
    if not created and instance.risk_type is not None and not int(instance.risk_type):
        contracts = instance.user.contract_set.get_discretionary_contracts().filter(orders__isnull=False)
        for contract in contracts:
            Notification.objects.create(
                user=instance.user,
                protocol=NotificationChoices.PROTOCOLS.sms,
                register=instance.user,
                topic=Topic.objects.get(name='notification'),
                title="투자운용 일시중지 알림",
                message="",
                context=MessageContextFactory(ResponseContext).get_context_dic(
                    instance=instance,
                    topic=NotiTopic.ACCOUNT_SUSPENTION,
                    status=NotiStatus.IS_STARTED,
                    step=NotiStep.STEP1,
                    product_code=ProductCode[contract.contract_type.code],
                    **{'context_fields': {'product_name': contract.contract_type.name}}
                )
            )
