from django.db.models import Max
from rest_framework import viewsets, filters

from api.bases.tendencies.models import Response
from api.versioned.v1.admin.tendencies.filters import ResponseFilter
from api.versioned.v1.admin.tendencies.serializers import (
    ResponseAdminSerializer
)

from common.viewsets import AdminViewSetMixin, MappingViewSetMixin


class ResponseAdminViewSet(AdminViewSetMixin,
                           MappingViewSetMixin,
                           viewsets.ModelViewSet):
    """
    list: [최근 투자성향분석 목록조회]
    가장 최근의 진행했던 투자성향 목록을 조회 합니다.

    """
    queryset = Response.objects.all().order_by('-created_at')
    serializer_class = ResponseAdminSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.OrderingFilter)
    filter_class = ResponseFilter

    def get_queryset(self):
        return self.queryset.values('user', 'user__profile__name', 'user__profile__risk_type').annotate(
            created_at=Max('created_at')).filter(user__is_active=True)
