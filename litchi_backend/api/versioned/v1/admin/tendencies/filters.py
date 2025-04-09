import django_filters

from api.bases.tendencies.models import Response


class ResponseFilter(django_filters.FilterSet):
    created_at_min = django_filters.DateTimeFilter(field_name='created_at',
                                                   lookup_expr='date__gte',
                                                   help_text='투자 성향분석 시작일')
    created_at_max = django_filters.DateTimeFilter(field_name='created_at',
                                                   lookup_expr='date__lte',
                                                   help_text='투자 성향분석 종료일')
    created_at_month = django_filters.NumberFilter(field_name='created_at__month',
                                                   help_text='투자 성향분석 완료월')
    created_at_day = django_filters.NumberFilter(field_name='created_at__day',
                                                 help_text='투자 성향분석 완료일')
    user__contract__contract_type__not = django_filters.CharFilter(field_name='user__contract__contract_type',
                                                                   exclude=True)

    class Meta:
        model = Response
        fields = ['created_at', 'type', 'user__contract__status', 'user__contract__contract_type__not']
