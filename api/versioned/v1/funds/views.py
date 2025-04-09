from rest_framework import viewsets, filters
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend

from api.bases.funds.models import *
from .serializers import (
    OperationListSerializer,
    OperationRetrieveSerializer,
    TradingSerializer
)
from .filters import (
    OperationListSearchFilter,
    TradingFilter
)


class OperationBaseViewSet(viewsets.ModelViewSet):
    queryset = Operation.objects.filter(end_date__isnull=True, liquidation_date__isnull=True).all() \
        .select_related('category_code').select_related('category_code__code')

    def dispatch(self, request, *args, **kwargs):
        return super(OperationBaseViewSet, self).dispatch(request, *args, **kwargs)


class OperationListViewSet(OperationBaseViewSet):
    """
    list:[펀드 검색]
    종목 이름 또는 코드를 사용하여 펀드 정보를 검색합니다.
    """
    serializer_class = OperationListSerializer
    filter_class = OperationListSearchFilter


class OperationRetrieveViewSet(OperationBaseViewSet):
    """
    retrieve:[펀드 종목 상세 조회]
    특정 종목 코드에 대한 펀드 상세 정보를 조회합니다.
    """
    serializer_class = OperationRetrieveSerializer
    lookup_field = 'symbol'


class TradingViewSet(viewsets.ModelViewSet):
    """
    list:[Trading 내역 조회]
    특정 종목 코드에 대한 Trading 내역을 조회합니다.
    """
    queryset = Trading.objects.all().order_by('-date')
    serializer_class = TradingSerializer
    ordering_fields = '__all__'

    def get_queryset(self):
        return self.queryset.filter(symbol__symbol=self.kwargs.get('symbol', None))

    def dispatch(self, request, *args, **kwargs):
        return super(TradingViewSet, self).dispatch(request, *args, **kwargs)
