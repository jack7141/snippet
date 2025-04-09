import django_filters
from django_filters.rest_framework import filterset
from django_filters.constants import STRICTNESS

from api.bases.portfolios.models import PortfolioDaily
from api.bases.etf_us.models import MarketIndex
from api.bases.contracts.models import ContractType

from common import filters


class PortfolioFilter(filters.FilterSet):
    port_date = django_filters.DateFilter(field_name='port_date', help_text='포트폴리오 조회 날짜', lookup_expr='lte')
    universe_index = django_filters.ChoiceFilter(field_name='port_type__universe_index__universe_index',
                                                 required=True, help_text='유니버스 구분',
                                                 choices=((1000, 'fund'),
                                                          (2001, 'etf'),
                                                          (2083, 'kb_etf_kr'),
                                                          (1003, 'mkfund'),
                                                          (2013, 'mketf'),
                                                          (1051, 'mkpension'),
                                                          (1080, 'oversea_etf'),
                                                          (1081, 'oversea_etf_display'),))

    strategy_code = django_filters.NumberFilter(field_name='port_type__strategy_code', help_text='전략코드')

    class Meta:
        model = PortfolioDaily
        fields = ['universe_index', 'strategy_code', 'port_date']
        strict = STRICTNESS.RAISE_VALIDATION_ERROR

    @property
    def qs(self):
        qs = super().qs
        strategy_code = self.data.get('strategy_code')

        if strategy_code is None:
            qs = qs.filter(port_type__strategy_code=0)
            return self._qs.filter(port_date=qs.first().port_date, port_type__strategy_code=0)
        else:
            return self._qs.filter(port_date=qs.first().port_date)


class MarketIndexFilter(filterset.FilterSet):
    symbol = django_filters.BaseInFilter(help_text='지수코드 - 콤마로 여러개 입력 가능', required=True)
    date = django_filters.DateTimeFilter(input_formats=['%Y-%m-%d'], required=True, lookup_expr='gte',
                                         help_text='조회 시작 기준일')

    class Meta:
        model = MarketIndex
        fields = ['symbol', 'date']


class MockInvestmentFilter(filterset.FilterSet):
    contract_type = django_filters.CharFilter(field_name='code', required=True, help_text='계약 종류(FA/EA/PA)')
    start_date = filters.FakeDateTimeFilter(input_formats=['%Y-%m-%d'], required=True, help_text='모의투자 시작일(YYYY-MM-DD)')
    end_date = filters.FakeDateTimeFilter(input_formats=['%Y-%m-%d'], required=False, help_text='모의투자 종료일(YYYY-MM-DD)')
    risk_type = filters.FakeNumberFilter(required=True, help_text='투자 위험도(성향)')
    rebalancing = filters.FakeBooleanFilter(help_text='리밸런싱 여부(true/false)')

    class Meta:
        model = ContractType
        fields = ['contract_type', 'start_date', 'end_date', 'risk_type', 'rebalancing']
        strict = STRICTNESS.RAISE_VALIDATION_ERROR
