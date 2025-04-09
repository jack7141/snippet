from django_filters import FilterSet
from api.bases.reports.models import ManagementReportHeader


class ManagementReportHeaderFilterSet(FilterSet):
    class Meta:
        model = ManagementReportHeader
        fields = ['year', 'quarter', 'strategy_code']
