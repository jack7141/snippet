import logging
from django.utils import timezone
from common.contexts import MessageContextFactory, NotiTopic, NotiStatus, NotiStep
from api.bases.orders.models import Order
from api.bases.notifications.models import Notification, Topic
from api.bases.notifications.choices import NotificationChoices
from api.bases.contracts.contexts import RebalancingContext
from api.bases.contracts.models import Contract, Rebalancing, ReservedAction
from api.bases.funds.utils import BDay
from api.bases.contracts.choices import ReservedActionChoices


try:
    DEFAULT_TOPIC = Topic.objects.get(name='notification')
except:
    DEFAULT_TOPIC = None

logger = logging.getLogger('django.server')


def get_reserve_time():
    return timezone.localtime().replace(hour=11, minute=0, second=0, microsecond=0) + BDay(1)


class RebalancingMixin(object):

    @staticmethod
    def add_reserve_action(contract, start_at=None):
        start_at = start_at or get_reserve_time()
        # 중복 등록 방지
        if ReservedAction.objects.filter(status=ReservedActionChoices.STATUS.reserved, contract=contract).exists():
            logger.info(f'already has rebalancing reserve action.')
            return False
        else:
            ReservedAction.objects.get_or_create(status=ReservedActionChoices.STATUS.reserved,
                                                 action=ReservedActionChoices.ACTIONS.rebalancing,
                                                 start_at=start_at,
                                                 contract=contract,
                                                 register=None)

            logger.info(f'add rebalancing reserve action. will start at {start_at}')
            return True

    @staticmethod
    def rebalancing_instance(contract,
                             topic=DEFAULT_TOPIC,
                             skip_save=False,
                             skip_send=False,
                             force_send=False,
                             note=None,
                             *args, **kwargs):
        """
        :param contract: 계약 instance
        :param topic: 알람 주제(기본은 `notification`)
        :param skip_save: rebalancing 필드 변경에 대한 저장 여부
        :param skip_send: 알람 전송 여부(계약의 현재 알람 가능상태는 별도)
        :param force_send: 계약의 현재 알람 가능상태를 무시하고 무조건 알람 발신
        :param args:
        :param kwargs:
        :return:
        """
        NPS = NotificationChoices.PROTOCOLS

        send_protocols = []
        result = {
            "send_protocols": send_protocols,
            "reserve": False,
            "contract": contract.id,
            "contract_type": contract.contract_type.code,
            "last_order": contract.last_order.completed_at,
            "account_alias": contract.account_alias,
        }

        # 지연 실행 리밸런싱인지 체크
        if contract.contract_type.delay_interval > 0:
            # 운용지시 내역이 있는지 확인. 내역이 없으면 리밸런싱 프로세스를 넘어간다.
            reserves = contract.reserved_actions.filter(action=ReservedActionChoices.ACTIONS.rebalancing,
                                                        status__in=[ReservedActionChoices.STATUS.reserved,
                                                                    ReservedActionChoices.STATUS.processing])
            if contract.order_history.exists():
                status = ReservedActionChoices.STATUS.processing

                #  운용지시 상태가 끝났는지 체크
                if contract.order_history.is_finish_order():
                    paid_at = contract.order_history.latest_finished_paid_at()
                    interval = contract.contract_type.delay_interval_value

                    # 운용지시가 끝난지 +n 일이 지나지 않은 경우 예약 실행 대기, 끝났으면 리밸런싱 시그널 처리함.
                    if timezone.now() > paid_at + interval:
                        status = ReservedActionChoices.STATUS.success #리밸런싱 시그널 처리

                if reserves.exists():
                    reserves.update(status=status)
                elif status == ReservedActionChoices.STATUS.processing:
                    reserves.create(status=status,
                                    action=ReservedActionChoices.ACTIONS.rebalancing,
                                    start_at=get_reserve_time(),
                                    contract=contract,
                                    register=None)
                if status == ReservedActionChoices.STATUS.processing:
                    result.update({'reserve': True})
                    return result
            else:
                skip_save = True
                skip_send = True

        if not skip_save:
            contract.rebalancing = True
            contract.save(update_fields=['rebalancing'])

            next_mode = contract.get_next_order_mode()

            if next_mode in [Order.MODES.rebalancing, Order.MODES.sell]:
                reb_instance, reb_created = Rebalancing.objects.get_or_create(contract=contract, sold_at__isnull=True)
            else:
                reb_instance, reb_created = Rebalancing.objects.get_or_create(contract=contract, bought_at__isnull=True)

            if reb_instance and reb_created:
                reb_instance.note = note
                reb_instance.save(update_fields=['note'])

            if not skip_send and (contract.check_for_notify() or force_send):
                if not contract.last_order.status == Order.STATUS.processing:
                    instance = Order(user=contract.user, order_rep=contract.vendor, order_item=contract,
                                     mode=contract.get_next_order_mode(), status=Order.STATUS.on_hold)

                    for protocol in [NPS.sms, NPS.push, NPS.app]:
                        msg = instance.get_notification_message(NPS[protocol])
                        if msg:
                            send_protocols.append(protocol)
                            notification = Notification.objects.create(
                                user=instance.user,
                                protocol=protocol,
                                register=instance.order_rep,
                                topic=topic,
                                title="리밸런싱 안내",
                                message=msg,
                                context=MessageContextFactory(RebalancingContext).get_context_dic(
                                    instance=reb_instance,
                                    topic=NotiTopic.REBALANCING, status=NotiStatus.IS_STAND_BY)
                            )
                            reb_instance.notifications.add(notification)
                        else:
                            logger.info('no message from {} contract(protocol : {})'.format(contract.id, protocol))
                else:
                    logger.info('{contract} - in processing at {created_at}'
                                .format(contract=contract.account_alias,
                                        created_at=contract.last_order.created_at))
            else:
                logger.info('skip send message to {} contract skip_send: {}, notify: {}, force_send: {}'.format(
                    str(contract), skip_send, contract.check_for_notify(), force_send))

        return result
