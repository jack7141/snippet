import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from api.bases.notifications.models import Notification, Topic
from api.bases.notifications.choices import NotificationChoices
from api.bases.orders.models import Order
from api.bases.orders.contexts import OrderContext
from api.bases.contracts.models import Rebalancing

from common.decorators import disable_for_loaddata
from common.contexts import MessageContextFactory

logger = logging.getLogger('django.server')


@receiver(post_save, sender=Order)
@disable_for_loaddata
def send_transition(sender, instance, created, **kwargs):
    try:
        completed_at = timezone.now()
        if instance.status in [Order.STATUS.canceled,
                               Order.STATUS.completed,
                               Order.STATUS.skipped] and not instance.completed_at:
            Order.objects.filter(id=instance.id).update(completed_at=completed_at)

        NPS = NotificationChoices.PROTOCOLS
        topic = Topic.objects.get(name='notification')

        if instance.is_status_changed() or created:

            reb_qs = Rebalancing.objects.filter(contract=instance.order_item)
            reb = None

            if reb_qs.exists():
                reb = reb_qs.latest('created_at')

            for protocol in [NPS.sms,
                             NPS.push,
                             NPS.app]:

                msg = instance.get_notification_message(NPS[protocol])
                if msg:
                    notification = Notification.objects.create(
                        user=instance.user,
                        protocol=protocol,
                        register=instance.order_rep,
                        topic=topic,
                        title="주문 처리 안내",
                        message=msg,
                        context=MessageContextFactory(OrderContext).get_context_dic(instance=instance)
                    )

                    if reb:
                        reb.notifications.add(notification)

            if (instance.status is not Order.STATUS.failed) and instance.order_item.rebalancing:
                instance.order_item.rebalancing = False
                instance.order_item.save(update_fields=['rebalancing'])

            if reb and instance.status in [Order.STATUS.canceled,
                                           Order.STATUS.completed,
                                           Order.STATUS.skipped]:
                if instance.mode == Order.MODES.rebalancing:
                    reb.bought_at = completed_at
                    reb.sold_at = completed_at
                elif instance.mode == Order.MODES.sell:
                    reb.sold_at = completed_at
                elif instance.mode == Order.MODES.buy:
                    reb.bought_at = completed_at

                reb.save(update_fields=['bought_at', 'sold_at'])

    except Exception as e:
        logger.error(e)
