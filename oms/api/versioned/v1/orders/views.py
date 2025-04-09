from api.bases.orders.models import Event, OrderSetting
from .serializers import EventSerializer, OrderSettingSerializer
from rest_framework import viewsets, response
from .filters import EventFilter


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    retrieve:Event 조회

    해당 계좌의 Event를 조회합니다.
    ---

    list:Event 목록 조회

    Event 목록을 조회합니다.
    ---

    """

    serializer_class = EventSerializer
    queryset = Event.objects.all()

    filter_class = EventFilter
    lookup_field = "account_alias"
    lookup_url_kwarg = lookup_field

    def retrieve(self, request, *args, **kwargs):
        queryset = self.get_queryset().filter(**kwargs)
        serializer = self.get_serializer(queryset, many=True)
        return response.Response(serializer.data)


class OrderSettingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    retrieve:OrderSetting 조회

    해당 계좌의 OrderSetting를 조회합니다.
    ---

    list:OrderSetting 목록 조회

    OrderSetting 목록을 조회합니다.
    ---

    """

    serializer_class = OrderSettingSerializer
    queryset = OrderSetting.objects.all()

    lookup_field = "account"
    lookup_url_kwarg = "account_alias"
