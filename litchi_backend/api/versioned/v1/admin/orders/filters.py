import django_filters
from api.bases.orders.models import Order
from api.bases.contracts.models import Contract, ReservedAction
from common import filters
from django_filters import rest_framework as rest_filters


class CiFilter(filters.FilterSet):
    ci = django_filters.CharFilter(field_name='ci')


class OrderFilter(filters.FilterSet):
    class Meta:
        model = Order
        fields = ('user', 'user__email', 'mode', 'status')


class LastOrderModeFilter(django_filters.CharFilter):
    def filter(self, qs, value):
        if value:
            return qs.filter(
                id__in=[item.id for item in qs if item.last_order and item.last_order.mode == value])
        else:
            return qs


class LastOrderStatusFilter(django_filters.NumberFilter):
    def filter(self, qs, value):
        if value is not None:
            return qs.filter(
                id__in=[item.id for item in qs if item.last_order and item.last_order.status == value])
        else:
            return qs


class NextOrderModeFilter(django_filters.CharFilter):
    def filter(self, qs, value):
        if value:
            return qs.filter(
                id__in=[item.id for item in qs if item.get_next_order_mode() == value])
        else:
            return qs


class ContractIdFilter(django_filters.CharFilter):
    def filter(self, qs, value):
        if value:
            qs = qs.filter(id__in=value.split(','))
        return qs


class ContractFilter(filters.FilterSet):
    contract_ids = ContractIdFilter(help_text='계약 ID 목록 (,로 구분)')
    last_order_mode = LastOrderModeFilter(required=False)
    last_order_status = LastOrderStatusFilter(required=False)
    next_order_mode = NextOrderModeFilter()

    class Meta:
        model = Contract
        fields = ('contract_ids', 'contract_type', 'last_order_mode', 'last_order_status', 'next_order_mode')


class ReservedActionFilter(rest_filters.FilterSet):
    class Meta:
        model = ReservedAction
        fields = ('status', 'action')
