import logging
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

from rest_framework import viewsets, filters, status
from rest_framework.response import Response

from common.viewsets import MappingViewSetMixin

from api.bases.contracts.models import Contract
from api.bases.orders.models import (
    Order, OrderDetail
)

from .serializers import (
    OrderSerializer,
    OrderBasketSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer
)

from .filters import (
    OrderDetailFilter
)

logger = logging.getLogger('django.server')


class OrderViewSet(MappingViewSetMixin,
                   viewsets.ModelViewSet):
    """
    list: [주문 내역 조회]

    create: [주문 처리 등록]
    신규주문을 등록합니다. </br>
    등록 조건은 다음과 같습니다. </br>
    1. 정상 계약 상태(status: 1) </br>
    2. 계약 타입이 주문 가능한 타입일 경우 </br>
    3. 기존 주문 내역이 없는 경우 </br>
    """
    queryset = Order.objects.all().select_related('order_item', 'user', 'order_rep')
    serializer_class = OrderSerializer

    serializer_action_map = {
        'create': OrderCreateSerializer
    }

    filter_fields = ('order_item', 'mode')

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class OrderBasketViewSet(MappingViewSetMixin,
                         viewsets.ModelViewSet):
    """
    retrieve: [주문 Basket 조회]
    """
    queryset = Order.objects.all().select_related('order_item', 'user', 'order_rep')
    serializer_class = OrderBasketSerializer

    filter_fields = ('order_item', 'mode')
    lookup_field = 'order_item'

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = Contract.objects.get(id=self.kwargs[self.lookup_field])
        serializer = self.get_serializer(instance)
        return Response(data=serializer.data, status=status.HTTP_200_OK)


class OrderDetailViewSet(MappingViewSetMixin,
                         viewsets.ModelViewSet):
    """
    list: [주문 체결 내역 조회]
    주문 체결내역을 조회합니다. 동일 요청에대해 1분간 서버 캐시가 적용됩니다. </br>
    자문/일임 구분없이 전체 체결내역이 조회됩니다. </br>
    최근 날짜 기준으로 제공됩니다. </br>
    DB에 존재하지 않는 종목의 경우 종목명에 null값으로 존재 할 수 있습니다. </br>

    created_at, ordered_at, paid_at 기준으로 필터링시에는 해당 당일만 조회 가능합니다. </br>
    created_at, ordered_at, paid_at 기준으로 ordering 가능합니다.**(기본값: -created_at)**</br>

    ```
    Ascending : created_at, ordered_at, paid_at (부호: 없음)
    Descending : -created_at, -ordered_at, -paid_at(부호: -)
    ```

    | **매매구분** |  | **체결구분** |  |
    |:-:|:-:|:-:|:-:|
    | **status** | **defs** | **status** | **defs** |
    | 1 | 매수 | 1 | 성공 |
    | 2 | 매도 | 2 | 실패 |
    |  |  | 3 | 취소 |
    |  |  | 4 | 대기 |
    """

    queryset = OrderDetail.objects.select_related('account_alias',
                                                  'account_alias__contract_type',
                                                  'account_alias__user').all().order_by('-created_at')

    serializer_class = OrderDetailSerializer
    filter_class = OrderDetailFilter
    filter_backends = (filters.DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ('created_at', 'ordered_at', 'paid_at')

    def get_queryset(self):
        return self.queryset.filter(account_alias__user=self.request.user)

    @method_decorator(cache_page(60))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
