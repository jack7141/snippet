from rest_framework import viewsets, filters
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

from api.bases.authentications.models import Auth

from common.viewsets import MappingViewSetMixin, AdminViewSetMixin

from .serializers import (
    AuthenticationsSerializer,
    AuthAccountSerializer
)


class AuthenticationsAdminViewSet(MappingViewSetMixin,
                                  AdminViewSetMixin,
                                  viewsets.ModelViewSet):
    """
    list:[ARS인증번호 조회]
    각 계약 건에 대한 인증을 조회합니다. <br/>
    * 검색 가능한 필드 : 계약 아이디
    """
    serializer_class = AuthenticationsSerializer
    queryset = Auth.objects.filter(cert_type=3, is_verified=True, etc_3__isnull=False)
    filter_backends = (filters.SearchFilter,)
    search_fields = ('etc_2',)


class AuthAccountAdminViewSet(MappingViewSetMixin,
                              AdminViewSetMixin,
                              viewsets.ModelViewSet):
    """
    partial_update:[수수료 계좌 업데이트]
    수수료 계좌 인증이 완료되었으나 디비에 값이 없을 경우 값을 입력하여 업데이트합니다.

    etc_2 : contract_id
    """
    serializer_class = AuthAccountSerializer
    queryset = Auth.objects.filter(cert_type=3, is_verified=True, is_expired=False)
    lookup_field = 'etc_2'

    def filter_queryset(self, queryset):
        return self.queryset.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        qs = self.get_queryset()
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        qs = qs.filter(**filter_kwargs)

        if not qs.exists():
            raise NotFound("No Account registered")

        qs = qs.last()

        serializer = self.get_serializer(instance=qs, data=request.data)
        serializer.is_valid(raise_exception=True)

        self.perform_update(serializer)
        return Response(serializer.data)
