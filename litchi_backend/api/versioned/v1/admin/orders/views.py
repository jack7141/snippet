from rest_framework import viewsets, status
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import F, DateTimeField, Count

from api.versioned.v1.orders.views import OrderViewSet
from api.bases.contracts.models import Contract, ReservedAction
from api.bases.contracts.mixins import RebalancingMixin
from api.bases.orders.models import Order
from api.bases.contracts.choices import ReservedActionChoices

from .serializers import (
    AdminOrderSerializer,
    AdminRebalancingSerializer,
    AdminRebalancingWithNoteSerializer,
    AdminRebalancingNotifySerializer,
    AdminBulkOrderSerializer,
    AdminReservedActionSerializer
)

from .filters import OrderFilter, ContractFilter, ReservedActionFilter
from common.viewsets import MappingViewSetMixin, AdminViewSetMixin
from common.exceptions import PreconditionFailed, PreconditionRequired


class AdminOrderViewSet(AdminViewSetMixin, OrderViewSet):
    """
    list:[전체 주문 목록 조회]
    mode가 'rebalancing'이며 status가 'on-hold'인 경우 현재 리밸런싱 대상자로 선정 되었으나 처리 완료되지 않은 주문입니다.</br>
    최초 주문(mode:'new_order')의 경우 created_at 정보와 completed_at가 동일 할 수 있습니다.
    create:[주문 단일 생성 및 처리]
    notify:[리밸런싱 대상자에게 알람 발생]
    현재 일로부터 리밸런싱 발생일 5일이하인 주문에 대해 알람을 보냅니다.
    """
    serializer_class = AdminOrderSerializer
    filter_class = OrderFilter

    def get_queryset(self):
        return self.queryset

    def notify(self, request, *args, **kwargs):
        mode = request.query_params.get('mode', Order.MODES.rebalancing)
        one_day = timezone.timedelta(days=1)
        five_days = timezone.timedelta(days=5)
        notify_min = F('created_at') + one_day
        notify_min.output_field = DateTimeField()

        notify_limit = F('created_at') + five_days
        notify_limit.output_field = DateTimeField()

        queryset = self.get_queryset() \
            .filter(status__in=[Order.STATUS.on_hold, Order.STATUS.failed]) \
            .annotate(notify_min=notify_min, notify_limit=notify_limit) \
            .filter(notify_min__lte=timezone.now(), notify_limit__gte=timezone.now(), mode=mode)

        for item in queryset:
            item.status = Order.STATUS.on_hold
            item.save()

        return Response(data=AdminOrderSerializer(queryset, many=True).data)


class AdminOrderBulkViewSet(AdminViewSetMixin,
                            viewsets.ModelViewSet):
    """
    list:[주문 전체목록 조회]
    create:[여러 주문 일괄 처리]
    """
    queryset = Order.objects.all()
    serializer_class = AdminBulkOrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(data=serializer.data)


class AdminRebalancingViewSet(MappingViewSetMixin,
                              AdminViewSetMixin,
                              RebalancingMixin,
                              viewsets.ModelViewSet):
    """
    create:[리밸런싱 대상 주문 생성]
    계약 단위의 주문 내역중 가장 최근 주문 완료일자에 해당하는 아이템의 상태가 리밸런싱 지정일이 지난경우 리밸런싱 대상자로 선정됩니다.</br>
    리밸런싱 대상자로 선정 된 후, 알람 재전송 가능일 이내에 요청된 경우 대상자들에게 알람을 발송합니다.</br></br>
    skip_save - rebalancing 필드 변경에 대한 저장 여부<br/>
    skip_send - 알람 전송 여부(계약의 현재 알람 가능상태는 별도)<br/>
    force_send - 계약의 현재 알람 가능상태를 무시하고 무조건 알람 발신<br/>

    ```
    ex) 리밸런싱 기준일: 30일, 재전송 가능일: 5일
    0                       30     35               60                      90      100
    |-----------------------|-----------------------|-----------------------|--------|
    주문완료일                 ↑      ↑                                                오늘
                         리밸런싱  최대알람처리일
    ```

    list:[리밸런싱 대상자 조회 - 유저 기준]
    전체 유저 중 주문 정보의 status가 'on-hold'를 가진 유저 목록을 제공합니다.

    contract:[계약 기준 리밸런싱 강제 실행]

    """
    serializer_class = AdminRebalancingSerializer
    queryset = Contract.objects.filter(orders__isnull=False).prefetch_related('contract_type')
    filter_class = ContractFilter
    serializer_action_map = {
        'list': AdminRebalancingNotifySerializer,
        'contract': AdminRebalancingWithNoteSerializer
    }

    def get_queryset(self):
        contract_type = self.request.query_params.get('contract_type')
        if self.action != 'contract':
            return Contract.objects.get_rebalancing_contracts(contract_type)
        else:
            return Contract.objects.get_active_contracts(contract_type)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.data.get('ignore_interval'):
            queryset = self.filter_queryset(self.queryset)
        else:
            queryset = self.filter_queryset(self.get_queryset())

        result = []

        for item in queryset:
            result.append(self.rebalancing_instance(item, **serializer.data))

        reb_result = {
            "notified_count": len([item for item in result if len(item.get('send_protocols', 0))]),
            "result": result
        }

        return Response(reb_result, status=201)

    def contract(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = self.get_object()

        if not instance.last_order or instance.last_order.status not in [Order.STATUS.completed,
                                                                         Order.STATUS.canceled,
                                                                         Order.STATUS.failed,
                                                                         Order.STATUS.skipped]:

            if instance.last_order:
                raise PreconditionFailed(detail={
                    'last_order': instance.last_order.id,
                    'last_order_status': instance.last_order.status
                })
            else:
                raise PreconditionRequired(detail='%s item does not meet conditions.' % str(instance))

        result = []

        result.append(self.rebalancing_instance(instance, **serializer.data))

        reb_result = {
            "notified_count": len([item for item in result if len(item.get('send_protocols', 0))]),
            "result": result
        }

        return Response(reb_result, status=201)


class AdminRebalancingNotifyViewSet(AdminRebalancingViewSet):
    """
    list:[리밸런싱 알림 대상자 목록 조회]
    create:[리밸런싱 알림 전송]
    전체 리밸런싱 대상자들에게 알림을 전송합니다. 알림 전송시 알람 전송기간 여부를 무시하고 알람을 전송합니다.<br/>
    알람 전송 조건: reb_required == True
    """

    def get_queryset(self):
        contract_type = self.request.query_params.get('contract_type')
        return Contract.objects.get_reb_notify_only(contract_type)


class AdminReservedActionViewSet(AdminViewSetMixin,
                                 RebalancingMixin,
                                 viewsets.ModelViewSet):
    """
    create:[예약 실행]
    예약 등록된 계약의 특정 동작을 수행합니다.
    """
    queryset = ReservedAction.objects.all().prefetch_related('contract', 'contract__contract_type')
    serializer_class = AdminReservedActionSerializer

    def get_queryset(self):
        if self.action == 'create':
            return super().get_queryset().filter(
                    contract__isnull=False,
                    status__in=[
                        ReservedActionChoices.STATUS.reserved,
                        ReservedActionChoices.STATUS.processing
                    ])
        else:
            return super().get_queryset()

    def create(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        result = []
        for item in queryset:
            result.append(self.rebalancing_instance(item.contract))

        reb_result = {
            "notified_count": len([item for item in result if len(item.get('send_protocols', 0))]),
            "result": result
        }

        return Response(reb_result, status=201)
