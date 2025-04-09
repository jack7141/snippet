import django_filters
from django_filters.widgets import RangeWidget, SuffixedMultiWidget
from django.contrib.auth import get_user_model

from api.bases.contracts.models import Contract, Transfer
from api.bases.orders.models import Order


class UserSearchFilter(django_filters.FilterSet):
    username = django_filters.CharFilter(field_name='profile__name', help_text='유저명')
    phone = django_filters.CharFilter(field_name='profile__phone', help_text='전화번호')
    email = django_filters.CharFilter(help_text='이메일')

    class Meta:
        model = get_user_model()
        fields = ['username', 'phone', 'email']


class DurationRangeWidget(SuffixedMultiWidget, RangeWidget):
    suffixes = ['min', 'max']


# Todo: 개별 Filter를 묶음 FilterBackend로 변경
class UserBasedContractDateRangeFilter(django_filters.FilterSet):
    created_at = django_filters.DateTimeFromToRangeFilter(widget=DurationRangeWidget,
                                                          help_text='created_at_min, created_at_max',
                                                          field_name='contract__created_at')

    class Meta:
        model = get_user_model()
        fields = ['created_at', ]


class ContractSearchFilter(django_filters.FilterSet):
    created_at = django_filters.DateTimeFromToRangeFilter(widget=DurationRangeWidget,
                                                          help_text='created_at_min, created_at_max')
    effective_date_min = django_filters.DateTimeFilter(field_name='orders__created_at__date__gte',
                                                       help_text='계약 발효일 시작(최초 주문 생성일)',
                                                       method='filter_effective_date')
    effective_date_max = django_filters.DateTimeFilter(field_name='orders__created_at__date__lte',
                                                       help_text='계약 발효일 종료(최초 주문 생성일)',
                                                       method='filter_effective_date')
    effective_date_month = django_filters.NumberFilter(field_name='orders__created_at__month',
                                                       help_text='계약 발효일 월(최초 주문 생성일)',
                                                       method='filter_effective_date')
    effective_date_day = django_filters.NumberFilter(field_name='orders__created_at__day',
                                                     help_text='계약 발효일 일(최초 주문 생성일)',
                                                     method='filter_effective_date')
    contract_type__not = django_filters.CharFilter(field_name='contract_type', exclude=True)
    status__not = django_filters.CharFilter(field_name='status', exclude=True)
    term__field_1 = django_filters.CharFilter(field_name='term__field_1', help_text='계약 약관 버전')

    def filter_effective_date(self, queryset, key, value):
        if value:
            filter_kwargs = {
                key: value,
                'orders__mode': 'new_order'
            }
            return queryset.filter(**filter_kwargs).distinct()
        return queryset

    class Meta:
        model = Contract
        fields = ['created_at', 'contract_type', 'contract_type__not', 'user', 'risk_type', 'status', 'status__not',
                  'term__field_1']


class ContractDeletionFilter(django_filters.FilterSet):
    canceled_at = django_filters.DateTimeFilter(lookup_expr='lt', required=True)

    class Meta:
        model = Contract
        fields = ['canceled_at']


class UserDateRangeFilter(django_filters.FilterSet):
    created_at = django_filters.DateTimeFromToRangeFilter(widget=DurationRangeWidget,
                                                          help_text='created_at_min, created_at_max',
                                                          field_name='date_joined')

    class Meta:
        model = get_user_model()
        fields = ['created_at']


class OrderDateRangeFilter(django_filters.FilterSet):
    created_at = django_filters.DateTimeFromToRangeFilter(widget=DurationRangeWidget,
                                                          help_text='created_at_min, created_at_max')

    class Meta:
        model = Order
        fields = ['created_at']


class TransferFilter(django_filters.FilterSet):
    completed_at__isnull = django_filters.BooleanFilter(name='completed_at',
                                                        lookup_expr='isnull')
    canceled_at__isnull = django_filters.BooleanFilter(name='canceled_at',
                                                       lookup_expr='isnull')

    class Meta:
        model = Transfer
        fields = '__all__'
