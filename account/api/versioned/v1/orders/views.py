import logging

from rest_framework import viewsets, mixins

from api.bases.orders.models import Event, OrderDetail
from common.exceptions import PreconditionFailed
from common.viewsets import MappingViewSetMixin
from .filters import (
    OrderEventFilter,
)
from .serializers import (
    OrderEventSerializer, OrderEventCreateSerializer, OrderEventUpdatePortSerializer, OrderDetailSerializer
)

logger = logging.getLogger('django.server')


class OrderViewSet(MappingViewSetMixin,
                   mixins.CreateModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.DestroyModelMixin,
                   viewsets.ReadOnlyModelViewSet):
    """
    create:주문 생성

    계좌의 주문을 생성합니다.
    ---

    list:전체 주문 내역 조회

    전체 계좌의 주문 내역을 조회합니다.
    ---

    retrieve:주문 내역 조회

    계좌의 주문 내역을 조회합니다.
    ---

    partial_update:주문 포트폴리오 변경

    대기중인 주문 포트폴리오 ID를 변경합니다.
    ---
    계좌의 포트폴리오 ID도 같이 변경됩니다.
    (대기중인 주문만 업데이트 허용)

    destroy:주문 취소

    대기중 혹은 진행중인 주문 취소 처리
    ---
    대기중 혹은 진행중인 주문을 취소처리합니다.
    """

    queryset = Event.objects.all()
    serializer_class = OrderEventSerializer
    filterset_class = OrderEventFilter
    serializer_action_map = {
        'partial_update': OrderEventUpdatePortSerializer,
        'update': OrderEventUpdatePortSerializer,
        'create': OrderEventCreateSerializer
    }

    def perform_destroy(self, instance):
        if instance.status in [Event.STATUS.on_hold, Event.STATUS.processing]:
            instance.status = Event.STATUS.canceled
        else:
            raise PreconditionFailed(
                f"Event({instance.get_mode_display(), instance.get_status_display()}) "
                f"must be one of [on_hold, processing] to cancel")
        instance.save(update_fields=['status'])


class OrderDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list:전체 주문 상세내역 조회

    전체 계좌의 주문 상세내역을 조회합니다.
    ---

    retrieve:계좌 주문 상세내역 조회

    계좌의 주문 상세내역 조회합니다.
    """
    queryset = OrderDetail.objects.all()
    serializer_class = OrderDetailSerializer
    filter_fields = ('account_alias',)
