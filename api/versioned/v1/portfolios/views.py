import json
import pandas as pd

from django.views.decorators.cache import cache_page
from django.utils import timezone
from django.utils.decorators import method_decorator
from rest_framework import viewsets, filters, status, permissions
from rest_framework.response import Response
from dateutil.relativedelta import relativedelta

from api.bases.portfolios.models import PortfolioDaily
from api.bases.etf_us.models import MarketIndex
from api.bases.contracts.models import ContractType

from .serializers import (
    PortfolioWrapSerializer,
    PortfolioForGuestWrapSerializer,
    MarketIndexSerializer,
    MarketIndexTradingSerializer,
    MockInvestmentSerializer
)

from api.versioned.v1.portfolios.filters import (
    PortfolioFilter,
    MarketIndexFilter,
    MockInvestmentFilter
)

from common.analytics import AnalyticsInvestment


class PortfolioViewSet(viewsets.ModelViewSet):
    """
    retrieve:[포트폴리오 조회]
    포트폴리오를 조회합니다. 조회시 포트폴리오의 universe값이 필요하며, 특정 날짜의 포트폴리오도 조회 가능합니다.<br/>
    날짜 기준으로 조회시 해당 날짜에 포트폴리오가 존재하지 않는 경우 과거 포트폴리오중 요청받은 포트폴리오 날짜와 가장 가까운 날짜의 포트폴리오가
    제공됩니다.
    """
    queryset = PortfolioDaily.objects.all().select_related('port_type')
    serializer_class = PortfolioWrapSerializer
    filter_class = PortfolioFilter

    @method_decorator(cache_page(600))
    def dispatch(self, request, *args, **kwargs):
        return super(PortfolioViewSet, self).dispatch(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        sample = queryset.first()

        serializer = self.get_serializer({
            'date': sample.port_date,
            'universe_index': sample.universe_index,
            'portfolios': queryset
        })

        return Response(serializer.data)


class PortfolioGuestViewSet(PortfolioViewSet):
    """
    retrieve:[포트폴리오 조회]

    추가 인증 없이, 포트폴리오 조회 요청을 합니다.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PortfolioForGuestWrapSerializer


class MarketIndexViewSet(viewsets.ModelViewSet):
    """
    list:[지수 종목 조회]
    """
    queryset = MarketIndex.objects.values('symbol').distinct().values('symbol', 'name').order_by('symbol')
    serializer_class = MarketIndexSerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ('$symbol', '$name')


class MarketIndexTradingViewSet(viewsets.ModelViewSet):
    """
    list:[지수 종목 가격 조회]

    특정 지수들의 가격 정보를 조회합니다. 조회시 지수코드는 한번에 여러개 입력가능하며,
    date 기준으로 각 종목의 Trading 시계열 데이터를 제공합니다.
    > ex: ?code=SP50,183657&date=2019-08-01
    """
    queryset = MarketIndex.objects.all().order_by('symbol')
    serializer_class = MarketIndexTradingSerializer
    filter_class = MarketIndexFilter

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        qs = queryset.values('symbol', 'name').distinct()

        for item in qs:
            item.update({'tradings': queryset.filter(**item)})

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MockInvestmentViewSet(viewsets.ModelViewSet):
    """
    retrieve:[모의투자]
    계약 종류를 선택하여 해당 계약의 모의투자 결과를 조회합니다.
    """
    queryset = ContractType.objects.all()
    serializer_class = MockInvestmentSerializer
    filter_class = MockInvestmentFilter

    def filter_fields(self, queryset):
        filter_class = self.filter_class(self.request.query_params, queryset=queryset, request=self.request)
        filter_class.form.is_valid()
        return filter_class.form.cleaned_data

    @method_decorator(cache_page(600))
    def retrieve(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        filter_fields = self.filter_fields(queryset)
        now = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        ev = None

        if queryset.exists():
            contract_type = queryset.first()
            universe_index = contract_type.universe
            interval = contract_type.reb_interval_value
            start_date = filter_fields.get('start_date')
            end_date = filter_fields.get('end_date')
            if (not end_date) or end_date >= now:
                end_date = now - relativedelta(days=1)
            risk_type = filter_fields.get('risk_type')
            rebalancing = bool(filter_fields.get('rebalancing'))

            ports = []

            while start_date < end_date:
                _from = start_date

                qs = PortfolioDaily.objects.get_portfolio(universe_index=universe_index,
                                                          port_date=start_date,
                                                          risk_type=risk_type)

                if not qs.exists():
                    break

                if rebalancing:
                    start_date += interval

                    if start_date > end_date:
                        start_date = end_date
                else:
                    start_date = end_date

                if start_date.weekday() > 4:
                    start_date += relativedelta(days=7 - start_date.weekday())

                _to = start_date

                port = qs.get()

                ports.append({'port_data': port.port_data, 'port_date': _from})
                port.set_trading_dataframe(_from, _to)

                if ev is None:
                    ev = port.evaluation_amount()
                else:
                    ev = pd.concat([ev, port.evaluation_amount(ev.sum(axis=1)[-1])], sort=False)

            if ev is None or ev.empty:
                return Response(status=status.HTTP_404_NOT_FOUND)
            ev.index = ev.index.tz_localize(tz='Asia/Seoul')
            data = ev[~ev.index.duplicated(keep='first')]
            ai = AnalyticsInvestment(data)
            return Response({
                'evaluation_amount': json.loads(ai.evaluation_amount.astype(int).to_json()),
                'reb_count': len(ports) - 1
            })
        return Response(status=status.HTTP_404_NOT_FOUND)
