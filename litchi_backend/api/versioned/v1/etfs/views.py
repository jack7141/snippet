from rest_framework import viewsets
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

from api.bases.etf_kr.models import *
from .serializers import (
    OperationListSerializer,
    OperationRetrieveSerializer,
    TradingSerializer
)


class OperationBaseViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()

    def dispatch(self, request, *args, **kwargs):
        return super(OperationBaseViewSet, self).dispatch(request, *args, **kwargs)


class OperationListViewSet(OperationBaseViewSet):
    """
    list:[ETF 검색]
    종목 이름 또는 코드를 사용하여 ETF 정보를 검색합니다.
    """
    serializer_class = OperationListSerializer


class OperationRetrieveViewSet(OperationBaseViewSet):
    """
    retrieve:[ETF 종목 상세 조회]
    특정 종목 코드에 대한 펀드 상세 정보를 조회합니다.
    """
    serializer_class = OperationRetrieveSerializer
    lookup_field = 'isin'


class TradingViewSet(viewsets.ModelViewSet):
    """
    list:[Trading 내역 조회]
    특정 종목 코드에 대한 Trading 내역을 조회합니다.
    """
    queryset = Trading.objects.all().order_by('-date')
    serializer_class = TradingSerializer

    def get_queryset(self):
        isin = self.kwargs.get('isin', None)
        return self.queryset.filter(isin__isin=isin)

    def dispatch(self, request, *args, **kwargs):
        return super(TradingViewSet, self).dispatch(request, *args, **kwargs)
