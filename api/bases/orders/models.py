import uuid
import copy
import logging

from auditlog.registry import auditlog

from django.db import models
from django.db.models import Count, Case, When, IntegerField
from django.conf import settings
from django.template import Template, Context

from api.bases.contracts.models import Contract
from api.bases.contracts.choices import ContractChoices
from api.bases.funds.models import Operation
from api.bases.etf_kr.models import Profile
from api.bases.etf_us.models import Profile as USProfile
from api.bases.orders.choices import Risk, Messages, OrderDetailChoices

from model_utils.fields import StatusField

from common.decorators import cached_property
from common.utils import merge

logger = logging.getLogger('django.server')


class Order(models.Model):
    MODES = ContractChoices.ORDER_MODES
    STATUS = ContractChoices.ORDER_STATUS

    id = models.UUIDField(default=uuid.uuid4, editable=False, auto_created=True, unique=True, primary_key=True)
    mode = StatusField(choices_name='MODES', null=False, blank=False, help_text='주문 구분', default=MODES.new_order)
    created_at = models.DateTimeField(auto_now_add=True, help_text='주문 일자')
    updated_at = models.DateTimeField(auto_now=True, help_text='업데이트 일자')
    completed_at = models.DateTimeField(blank=True, null=True, help_text='주문 완료 일자')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE,
                             help_text='고객', related_name='orders')
    order_item = models.ForeignKey(Contract, blank=True, null=True, help_text='계약사항', on_delete=models.CASCADE,
                                   related_name='orders')
    order_rep = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL,
                                  help_text='주문 처리 계정 id', related_name='order_reps')
    status = models.IntegerField(choices=STATUS, blank=True, null=True, help_text='주문 상태')

    class Meta:
        ordering = ('-created_at', '-completed_at')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__status = self.status

    def __str__(self):
        try:
            return '{user}({contract}-{mode}-{status})'.format(
                user=self.user,
                contract=self.order_item if self.order_item else None,
                mode=self.MODES[self.mode],
                status=self.STATUS[self.status] if self.status else None)
        except:
            return str(self.id)

    def is_status_changed(self):
        return self.__status != self.status

    @cached_property
    def message_template(self):
        source = Messages.TYPE_MESSAGES.get(self.order_item.contract_type, {})
        return merge(source, copy.deepcopy(Messages.MESSAGE_TEMPLATES))

    def get_notification_message(self, msg_type):
        if self.status in (Order.STATUS.failed,
                           Order.STATUS.on_hold,
                           Order.STATUS.processing,
                           Order.STATUS.completed,
                           Order.STATUS.skipped):

            msg_template = self.message_template.get(msg_type.lower(), {})
            message = '[{contract_type} | {risk_name}] 포트폴리오 {msg}'
            contract_type = self.order_item.contract_type.name
            risk_type = self.order_item.risk_type

            if msg_template.get(self.mode) and msg_template.get(self.mode).get(self.status):
                return message.format(
                    contract_type=contract_type,
                    risk_name=Risk.RISK_NAMES[risk_type],
                    msg=Template(msg_template[self.mode][self.status]).render(Context({'contract': self.order_item}))
                )
            else:
                return None


class OrderDetailManager(models.Manager):
    def latest_buy_order(self):
        return self.filter(ordered_at=self.latest('ordered_at').ordered_at, type=1)

    def latest_finished_paid_at(self, type=1):
        queryset = self.values('paid_at') \
            .filter(ordered_at=self.latest('ordered_at').ordered_at, type=type, paid_at__isnull=False)

        if queryset.exists():
            return queryset.latest('paid_at').get('paid_at')
        else:
            return None

    def latest_history_status(self):
        queryset = self.order_by().filter(type=1, order_price__gt=0).values('ordered_at').annotate(
            wait=Count(Case(When(paid_at__isnull=True, then=1), output_field=IntegerField())),
            done=Count(Case(When(paid_at__isnull=False, then=1), output_field=IntegerField())),
        )

        if queryset.exists():
            return queryset.latest('ordered_at')
        else:
            return queryset

    def is_finish_order(self):
        """
        현재 매수중인 종목들이 전부 매수 됐는지 체크.(연금 기준으로만 적용됨)
        :return: boolean
        """
        latest_order_history = self.latest_history_status()
        wait = latest_order_history.get('wait')
        done = latest_order_history.get('done')
        return wait == done


class OrderDetail(models.Model):
    objects = OrderDetailManager()

    account_alias = models.ForeignKey(Contract, to_field='account_alias', on_delete=models.CASCADE,
                                      related_name='order_history')
    code = models.CharField(max_length=12, help_text='ISIN')
    type = models.PositiveSmallIntegerField(choices=OrderDetailChoices.TYPE, help_text='매수/환매 구분')
    ordered_at = models.DateTimeField(null=True, help_text='주문일시')
    order_price = models.DecimalField(max_digits=20, decimal_places=5, help_text='주문금액')
    paid_at = models.DateTimeField(null=True, help_text='결재일시')
    paid_price = models.DecimalField(max_digits=20, decimal_places=5, help_text='결재금액(세금 제외 최종정산 금액)')
    shares = models.IntegerField(help_text='좌수')
    result = models.PositiveSmallIntegerField(choices=OrderDetailChoices.RESULT, help_text='체결구분')
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')

    class Meta:
        unique_together = (('account_alias', 'ordered_at', 'code', 'type', 'created_at'),)
        db_table = 'orders_order_detail'

    @cached_property
    def asset(self):
        contract_type = self.account_alias.contract_type

        try:
            if contract_type.asset_type == 'kr_fund':
                return Operation.objects.get(symbol=self.code, end_date__isnull=True)
            elif contract_type.asset_type == 'kr_etf':
                return Profile.objects.filter(isin__contains=self.code).last()
            elif contract_type.asset_type == 'etf':
                return USProfile.objects.get(symbol=self.code)
            return None
        except:
            return None


auditlog.register(Order)
