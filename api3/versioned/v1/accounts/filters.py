from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django_filters.rest_framework import filterset, filters
from django_filters.rest_framework.backends import DjangoFilterBackend
from api.bases.accounts.models import Asset


class AccountAliasFilterSet(filterset.FilterSet):
    account_alias_id = filters.CharFilter(help_text="계좌 대체번호")


class DumpAccountFilterSet(filterset.FilterSet):
    vendor_code = filters.CharFilter(help_text='증권사 Code', default='kb')
    date = filters.DateTimeFilter(input_formats=['%Y%m%d'], field_name='created_at', method="date_filter",
                                  help_text='생성일')

    def __init__(self, data=None, *args, **kwargs):
        date = timezone.localtime().strftime('%Y%m%d')

        if not data.get('date'):
            data = data.copy()
            data.update({'date': date})
        super().__init__(data, *args, **kwargs)

    def date_filter(self, queryset, field_name, value):
        lookup_expr = 'lt'
        queryset = queryset.filter(**{
            f'{field_name}__{lookup_expr}': value + relativedelta(days=1)})

        self.request.parser_context.update({'date': value})
        return queryset


class TradePeriodFilterSet(AccountAliasFilterSet):
    from_date = filters.DateFilter(field_name='trd_date', lookup_expr='gte')
    to_date = filters.DateFilter(field_name='trd_date', lookup_expr='lte')


class ExecutionPeriodFilterSet(AccountAliasFilterSet):
    from_date = filters.DateFilter(field_name='order_date', lookup_expr='gte')
    to_date = filters.DateFilter(field_name='order_date', lookup_expr='lte')


class PeriodFilterSet(AccountAliasFilterSet):
    from_date = filters.DateFilter(field_name='created_at__date', lookup_expr='gte')
    to_date = filters.DateFilter(field_name='created_at__date', lookup_expr='lte')


class SumUpNameFilterSet(filterset.FilterSet):
    j_names = filters.CharFilter(field_name='j_name', lookup_expr='in', method='is_j_name_in')
    is_managed = filters.BooleanFilter(field_name='managed')

    def is_j_name_in(self, queryset, field_name, value):
        if not value:
            return queryset
        lookup_expr = self.filters['j_names'].lookup_expr
        queryset = queryset.filter(**{f"{field_name}__{lookup_expr}": value.split(',')})
        return queryset


class MappingDjangoFilterBackend(DjangoFilterBackend):
    def get_filter_class(self, view, queryset=None):
        filter_action_map = getattr(view, 'filter_action_map', {})
        filter_fields_action_map = getattr(view, 'filter_fields_action_map', {})
        filter_class = filter_action_map.get(view.action, None)
        filter_fields = filter_fields_action_map.get(view.action, None)
        if filter_class:
            filter_model = filter_class.Meta.model
            assert issubclass(queryset.model, filter_model), \
                'FilterSet model %s does not match queryset model %s' % \
                (filter_model, queryset.model)
            return filter_class
        if filter_fields:
            MetaBase = getattr(self.default_filter_set, 'Meta', object)
            class AutoFilterSet(self.default_filter_set):
                class Meta(MetaBase):
                    model = queryset.model
                    fields = filter_fields
            return AutoFilterSet
        return None


class AssetPeriodFilterSet(AccountAliasFilterSet):
    from_date = filters.DateFilter(field_name='created_at__date', lookup_expr='gte')
    to_date = filters.DateFilter(field_name='created_at__date', lookup_expr='lte')

    class Meta:
        model = Asset
        fields = ('')