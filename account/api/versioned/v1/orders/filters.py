from django_filters.rest_framework import filterset, filters

from api.bases.orders.models import Event, OrderDetail
from common.utils import gen_choice_desc


class PortDateFilter(filters.DateFilter):
    def filter(self, qs, value):
        if not value:
            return qs
        return qs.filter(portfolio_id__startswith=value.strftime("%Y%m%d"))


class ExcludePortDateFilter(filters.DateFilter):
    def filter(self, qs, value):
        if not value:
            return qs
        return qs.exclude(portfolio_id__startswith=value.strftime("%Y%m%d"))


class OrderEventFilter(filterset.FilterSet):
    account_alias = filters.CharFilter(help_text='계약 임시번호')
    status = filters.NumberFilter(help_text=gen_choice_desc('상태값', Event.STATUS))
    mode = filters.ChoiceFilter(field_name="mode", choices=Event.MODES,
                                help_text=gen_choice_desc("자산 구분", Event.MODES))
    completed_at__gte = filters.DateTimeFilter(field_name='completed_at', help_text='최소 주문완료일(%Y-%m-%d %H:%M:%S)',
                                               input_formats=['%Y-%m-%d %H:%M:%S'], lookup_expr='gte')
    completed_at__lte = filters.DateTimeFilter(field_name='completed_at', help_text='최대 주문완료일(%Y-%m-%d %H:%M:%S)',
                                               input_formats=['%Y-%m-%d %H:%M:%S'], lookup_expr='lte')
    port_date = PortDateFilter(help_text="포트 등록일")
    port_date__neq = ExcludePortDateFilter(help_text="해당 포트 등록일 이외 등록된 주문")

    class Meta:
        model = Event
        fields = ('account_alias', 'completed_at__gte', 'completed_at__lte')


class OrderDetailFilter(filterset.FilterSet):
    account_alias = filters.CharFilter()

    class Meta:
        model = OrderDetail
        fields = ('account_alias',)
