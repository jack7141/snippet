from rest_framework import mixins
from rest_framework import viewsets, response
from rest_framework.permissions import IsAdminUser


from api.bases.accounts.models import Account
from api.bases.managements.models import Queue, OrderLog, ErrorOccur

from .filters import OrderQueueFilter, OrderLogFilter, ErrorOccurFilter
from .serializers import (
    QueueSerializer,
    OrderBasketSerializer,
    OrderLogSerializer,
    SuspensionAccountSerializer,
    SuspensionAccountDetailSerializer,
    ErrorOccurSerializer,
    ErrorParamSerializer,
)
from common.mixins import RequiredOrderManagementMixin, GetObjectByPkMixin


class ErrorOccurViewSet(viewsets.ModelViewSet):

    """
    retrieve: 에러 계좌 현황 및 메뉴얼 조회

    에러 계좌에 대한 대응 메뉴얼에 대해 조회합니다.
    ---

    list: 에러 계좌 현황 및 메뉴얼 조회

    에러 계좌에 대한 대응 메뉴얼에 대해 조회합니다.
    ---
    """

    queryset = ErrorOccur.objects.all()
    serializer_class = ErrorOccurSerializer
    http_method_names = ["get"]
    filter_class = ErrorOccurFilter

    def list(self, request, *args, **kwargs):
        serializer = ErrorParamSerializer(data=self.request.query_params)
        serializer.is_valid(True)
        return super().list(request, *args, **kwargs)


class OrderBasketViewSet(
    RequiredOrderManagementMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    retrieve:각 모드별 주문시 OrderBasket 계산

    각 모드별 주문시 OrderBasket 계산합니다
    ---

    - mode: new_order, rebalancing, sell
    - account_alias: 계좌 별칭
    """

    queryset = Account.objects.all()
    serializer_class = OrderBasketSerializer
    permission_classes = [
        IsAdminUser,
    ]

    def retrieve(self, request, mode, *args, **kwargs):
        om = self.init_order_management(mode=mode)
        order_basket = om.order_basket[om.order_basket["new_shares"] != 0]

        serializer = self.get_serializer(
            {
                "order_basket": order_basket.reset_index().to_dict(orient="records"),
                "is_rebalancing_condition_met": om.is_rebalancing_condition_met,
                "account_number": om.account_number,
                "summary": om.get_summary().reset_index().to_dict(orient="records"),
                "base": om.base,
            }
        )
        return response.Response(serializer.data)


class OrderQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    retrieve:OrderQueue 조회

    해당 계좌의 OrderQueue 목록을 조회합니다.
    ---

    list:OrderQueue 목록 조회

    OrderQueue 목록 전체를 조회합니다.
    ---

    - mode:
      - bid: 매수
      - ask: 매도
    - status:
      - 1: 지연중
      - 2: 실패
      - 3: 대기중
      - 4: 진행중
      - 5: 완료됨
      - 6: 취소됨
      - 7: 건너뜀
    """

    queryset = Queue.objects.all()
    serializer_class = QueueSerializer
    lookup_field = "account_alias"
    lookup_url_kwarg = lookup_field
    filter_class = OrderQueueFilter
    permission_classes = [IsAdminUser]

    def retrieve(self, request, *args, **kwargs):
        filter_kwargs = {self.lookup_field: kwargs[self.lookup_url_kwarg]}
        qs = self.filter_queryset(self.get_queryset()).filter(**filter_kwargs)
        serializer = self.get_serializer(qs, many=True)
        return response.Response(serializer.data)


class OrderLogViewSet(GetObjectByPkMixin, viewsets.ReadOnlyModelViewSet):
    """
    retrieve:주문 로그 조회

    해당 계좌의 주문 내역을 조회합니다.
    ---

    - type:
      - 10: 매수 신청
      - 11: 매수 정정
      - 12: 매수 취소
      - 20: 매도 신청
      - 21: 매도 정정
      - 22: 매도 취소

    - status:
      - 1: 지연중
      - 2: 실패
      - 3: 대기중
      - 4: 진행중
      - 5: 완료됨
      - 6: 취소됨
      - 7: 건너뜀

    retrieve:주문 로그 전체 조회

    해당 계좌의 주문 내역을 조회합니다.
    ---

    - type:
      - 10: 매수 신청
      - 11: 매수 정정
      - 12: 매수 취소
      - 20: 매도 신청
      - 21: 매도 정정
      - 22: 매도 취소

    - status:
      - 1: 지연중
      - 2: 실패
      - 3: 대기중
      - 4: 진행중
      - 5: 완료됨
      - 6: 취소됨
      - 7: 건너뜀
    """

    queryset = OrderLog.objects.all()
    serializer_class = OrderLogSerializer
    lookup_field = "account_alias"
    lookup_url_kwarg = lookup_field
    filter_class = OrderLogFilter
    permission_classes = [
        IsAdminUser,
    ]

    def retrieve(self, request, account_alias, *args, **kwargs):
        queryset = self.filter_queryset(
            OrderLog.objects.filter(order__account_alias=account_alias)
        )
        serializer = OrderLogSerializer(queryset, many=True)
        return response.Response(serializer.data)


class SuspensionAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """
    retrieve:운용 중지 계좌 상세 조회

    해당 운용 중지 계좌를 상세 조회합니다.
    ---

    list:운용중지 계좌 목록 조회

    운용 중지된 계좌 목록을 조회합니다.
    ---
    """

    serializer_class_dic = {
        "retrieve": SuspensionAccountDetailSerializer,
        "list": SuspensionAccountSerializer,
    }
    queryset = Account.objects.filter(status=Account.STATUS.account_suspension)

    def get_serializer_class(self):
        return self.serializer_class_dic.get(self.action, SuspensionAccountSerializer)
