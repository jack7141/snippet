import django_filters

from api.bases.funds.models import Operation, Trading


class OperationListSearchFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains', help_text='종목 명')
    symbol = django_filters.CharFilter(help_text='종목 코드')

    class Meta:
        model = Operation
        fields = ['name', 'symbol']


class TradingFilter(django_filters.FilterSet):
    symbol = django_filters.CharFilter(field_name='symbol__symbol', required=True, help_text='종목 코드')

    class Meta:
        model = Trading
        fields = ['symbol']