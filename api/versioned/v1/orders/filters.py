from common import filters
from django_filters import filterset
from django_filters.constants import STRICTNESS
from api.bases.orders.models import OrderDetail
from api.bases.orders.choices import OrderDetailChoices


class OrderDetailFilter(filters.FilterSet):
    contract = filterset.UUIDFilter(field_name='account_alias__id', help_text='계약 ID')
    type = filterset.ChoiceFilter(choices=OrderDetailChoices.TYPE, help_text='매도/매수 구분')
    result = filterset.ChoiceFilter(choices=OrderDetailChoices.RESULT, help_text='체결구분')
    created_at = filterset.DateTimeFilter(input_formats=['%Y-%m-%d'], help_text='기준일(%Y-%m-%d)')
    ordered_at = filterset.DateTimeFilter(input_formats=['%Y-%m-%d'], help_text='주문일(%Y-%m-%d)')
    ordered_at_min = filterset.DateTimeFilter(field_name='ordered_at', lookup_expr="gte",
                                              help_text='최소 주문일(%Y-%m-%d %H:%i:%S)')
    ordered_at_max = filterset.DateTimeFilter(field_name='ordered_at', lookup_expr="lte",
                                              help_text='최대 주문일(%Y-%m-%d %H:%i:%S)')
    paid_at = filterset.DateTimeFilter(input_formats=['%Y-%m-%d'], help_text='체결일(%Y-%m-%d)')

    class Meta:
        model = OrderDetail
        fields = ['contract', 'type', 'result', 'created_at', 'ordered_at', 'paid_at', 'ordered_at_min',
                  'ordered_at_max']
        strict = STRICTNESS.RAISE_VALIDATION_ERROR
