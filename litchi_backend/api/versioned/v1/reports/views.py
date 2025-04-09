from django.shortcuts import get_object_or_404
from rest_framework import viewsets, response
from api.bases.reports.models import (
    ManagementReportHeader, ManagementReport
)
from api.bases.contracts.models import Contract
from api.versioned.v1.reports.filters import ManagementReportHeaderFilterSet
from api.versioned.v1.reports.serializers import (
    ManagementReportSerializer,
    ManagementReportDetailSerializer,
    ManagementReportHeaderSerializer,
    ManagementReportHeaderDetailSerializer,
)
from common.viewsets import MappingViewSetMixin


class ManagementReportHeaderViewSet(MappingViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    retrieve: [운용 보고서 Header 상세 조회]

    운용 보고서 Header 상세 조회합니다.
    ---

    list: [운용 보고서 Header 목록 조회]

    운용 보고서 Header 목록을 조회합니다.
    ---
    """
    queryset = ManagementReportHeader.objects.all()
    serializer_class = ManagementReportHeaderSerializer
    serializer_action_map = {
        'retrieve': ManagementReportHeaderDetailSerializer
    }
    filterset_class = ManagementReportHeaderFilterSet


class ManagementReportViewSet(MappingViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    retrieve: [운용보고서 상세 내역 조회]

    유저의 운용보고서 상세 내역을 조회합니다.

    list: [운용보고서 목록 조회]

    유저의 운용보고서 목록을 조회합니다.

    list_report_by_contract: [운용보고서 목록 조회]

    해당 계약의 운용보고서 목록을 조회합니다.

    """
    queryset = ManagementReport.objects.filter(is_published=True).order_by('-created_at')
    serializer_class = ManagementReportSerializer
    serializer_action_map = {
        'retrieve': ManagementReportDetailSerializer
    }

    def get_queryset(self):
        queryset = super(ManagementReportViewSet, self).get_queryset()
        queryset = queryset.filter(
            account_alias_id__in=list(self.request.user.contract_set.values_list('account_alias', flat=True))
        )
        return queryset

    def get_object(self):
        _contract_id = self.kwargs.pop('contract_id')
        _contract = get_object_or_404(Contract.objects.filter(user=self.request.user), pk=_contract_id)

        filter_kwargs = {
            'account_alias_id': _contract.account_alias,
            **self.kwargs
        }
        instance = get_object_or_404(self.get_queryset(), **filter_kwargs)
        setattr(instance, 'contract', _contract)
        return instance

    def list_report_by_contract(self, request, contract_id, *args, **kwargs):
        _contract = get_object_or_404(Contract.objects.filter(user=self.request.user), pk=contract_id)
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(account_alias_id=_contract.account_alias)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return response.Response(serializer.data)
