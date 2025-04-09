import logging
import requests as req
from rest_framework import viewsets, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Case, When

from api.bases.users.models import VendorProperty
from api.bases.contracts.models import ContractStatus, get_contract_status
from api.bases.orders.models import Order
from api.versioned.v1.contracts.views import ContractViewSet
from api.versioned.v1.orders.views import OrderViewSet

from urllib.parse import urljoin
from common.viewsets import MappingViewSetMixin
from common.permissions import IsVendorOrAdminUser
from common.exceptions import PreconditionFailed, PreconditionRequired

from .serializers import (
    UserContractSerializer,
    VendorContractSerializer,
    VendorOrderSerializer,
    VendorTokenReqSerializer,
    VendorTokenRespSerializer,
    ExchangeRateReqSeiralizer,
    ExchangeRateRespSeiralizer
)

logger = logging.getLogger('django.server')


class VendorContractViewSet(ContractViewSet):
    """
    retrieve: [계약 상세 조회]

    destroy: [계약 해지]
    요청한 계약에대해 해지처리를 합니다.</br>
    정상 해지의 경우 status(204)로 응답됩니다.</br>
    이미 해지된 경우 status(404)로 응답됩니다.</br>
    출금이체가 완료되지 않은 상태의 계약인 경우 status(428)로 응답됩니다.</br>
    """
    permission_classes = [IsVendorOrAdminUser]

    serializer_action_map = {
        'retrieve': VendorContractSerializer
    }

    def get_queryset(self):
        if self.request.user.is_vendor or self.request.user.is_staff:
            return self.queryset
        else:
            return self.queryset.filter(vendor=self.request.user)

    def perform_destroy(self, instance):
        if instance.is_canceled:
            raise NotFound("already canceled.")

        if instance.status.code is get_contract_status(type='vendor_wait_cancel', code=True):
            instance.is_canceled = True
            instance.status = ContractStatus.objects.get(type='canceled')
            instance.save()
        else:
            raise PreconditionRequired()


class VendorContractUserViewSet(MappingViewSetMixin,
                                viewsets.ModelViewSet):
    permission_classes = [IsVendorOrAdminUser]
    serializer_class = UserContractSerializer
    queryset = get_user_model().objects.all() \
        .select_related('profile') \
        .prefetch_related('contract_set', 'contract_set', 'contract_set__orders') \
        .annotate(contract_conunt=Count(Case(When(contract__is_canceled=False, then=1)))) \
        .filter(contract_conunt__gt=0)

    filter_fields = ('id',)

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        else:
            return self.queryset.filter(contract__vendor=self.request.user)


class VendorOrderViewSet(MappingViewSetMixin,
                         viewsets.ModelViewSet):
    queryset = Order.objects.all().select_related('order_item', 'user', 'order_rep')
    permission_classes = [IsVendorOrAdminUser]
    serializer_action_map = {
        'create': VendorOrderSerializer
    }

    def get_queryset(self):
        return self.queryset

    def create(self, request, *args, **kwargs):
        # Note: vendor 에서 mode 필드는 사용하나 값을 공백으로 넣은경우 rebalancing으로 우회 처리
        if request.data.get('mode', None) == "":
            request.data.update({"mode": Order.MODES.rebalancing})
            logger.warning('{path} passing property `mode` value is empty string ("")'.format(path=self.request.path))

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()


class VendorTokenViewSet(MappingViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    retrieve: [Vendor Token 발급]
    인증된 사용자에 대해 Vendor Token을 발급합니다.</br>
    정상 발급의 경우 status(200)로 응답됩니다.</br>
    VendorPropert가 존재하지 않는 경우 status(412)로 응답됩니다.</br>
    Vendor에 토큰 발급 URL이 존재하지 않는 경우 status(404)로 응답됩니다.</br>
    사용자 프로필이 없는 경우 status(428)로 응답됩니다.</br>
    """
    serializer_class = VendorTokenRespSerializer

    def retrieve(self, request, *args, **kwargs):
        vendor_code = kwargs.get('vendor_code', '')
        if not request.user and not request.user.profile:
            raise PreconditionRequired("request.user.profile must be defined")

        if not VendorProperty.objects.filter(code=vendor_code).exists():
            raise PreconditionFailed("VendorProperty must be defined")

        endpoint = f'/api/v1/{vendor_code}/token'

        headers = {'Content-Type': "application/json"}
        API_HOST = settings.FEP_API_BACKEND
        req_serializer = VendorTokenReqSerializer(request.user)

        api_url = urljoin(API_HOST, endpoint)
        resp = req.post(url=api_url, json=req_serializer.data, headers=headers)
        try:
            resp.raise_for_status()
        except Exception as e:
            return Response({"detail": f"{e}"}, status=resp.status_code)
        serializer = self.get_serializer(data=resp.json())
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class ExchangeRateViewSet(MappingViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    retrieve: [실시간 환율 조회]

    실시간 환율을 조회합니다(USD, 현재 KB TR API 사용)
    ---
    """
    serializer_class = ExchangeRateRespSeiralizer
    vendor_code = 'kb'

    def retrieve(self, request, *args, **kwargs):

        endpoint = f'/api/v1/{self.vendor_code}/exchange_rate'

        headers = {'Content-Type': "application/json"}
        API_HOST = settings.FEP_API_BACKEND
        req_serializer = ExchangeRateReqSeiralizer(request.user)

        api_url = urljoin(API_HOST, endpoint)
        resp = req.get(url=api_url, json=req_serializer.data, headers=headers)
        try:
            resp.raise_for_status()
        except Exception as e:
            return Response({"detail": f"{e}"}, status=resp.status_code)

        resp_serializer = self.get_serializer(resp.json())
        return Response(resp_serializer.data)
