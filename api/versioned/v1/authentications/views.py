import json
import logging

from django.conf import settings
from django.utils import timezone
from drf_openapi.utils import view_config

from rest_framework import viewsets, status
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.serializers import Serializer
from rest_framework.throttling import ScopedRateThrottle

from api.bases.authentications.models import Auth
from api.bases.authentications.choices import AuthenticationChoices
from api.bases.authentications.adapters import ktfc_adapter, ars_adapter, owner_adapter
from api.bases.contracts.models import Contract, get_contract_status

from .serializers import (
    SMSCertSerializer,
    SMSCertCreateSerializer,
    AccountCertSerializer,
    AccountCertCreateSerializer,
    OwnerCreateSerializer,
    AccountRealNameSerializer,
    CertValidRespSerializer,
    ARSCertSerializer,
    ARSCertCreateSerializer,
    AuthAccountSerializer
)

logger = logging.getLogger('django.server')


class CertBaseViewSet(viewsets.ModelViewSet):
    queryset = Auth.objects.all()
    serializer_action_map = {}
    permission_classes_map = {
        'list': [IsAdminUser]
    }

    throttle_classes_map = {
        'create': (ScopedRateThrottle,)
    }

    def get_permissions(self):
        permission_classes = self.permission_classes
        if self.permission_classes_map.get(self.action, None):
            permission_classes = self.permission_classes_map[self.action]

        return [permission() for permission in permission_classes]

    def get_throttles(self):
        throttle_classes = self.throttle_classes
        if self.throttle_classes_map.get(self.action, None):
            throttle_classes = self.throttle_classes_map[self.action]
        return [throttle() for throttle in throttle_classes]

    @property
    def cert_type(self):
        if not hasattr(self, '_cert_type'):
            _type = self.request.path.split('/')[4]
            _cert_type = None

            for item_key, item_value in AuthenticationChoices.AUTH_TYPES:
                if _type == item_value:
                    _cert_type = item_key
            self._cert_type = _cert_type
        return self._cert_type

    @property
    def expiration_delta(self):
        if not hasattr(self, '_expiration_delta'):
            if self.cert_type == '1':
                self._expiration_delta = timezone.timedelta(minutes=3)
            elif self.cert_type == '2':
                self._expiration_delta = timezone.timedelta(days=1)
            elif self.cert_type == '3':
                self._expiration_delta = timezone.timedelta(minutes=3)
        return self._expiration_delta

    def get_queryset(self):
        return self.queryset.filter(cert_type=self.cert_type)

    def get_serializer_class(self):
        if self.serializer_action_map.get(self.action, None):
            return self.serializer_action_map[self.action]
        return self.serializer_class

    def perform_create(self, serializer):
        queryset = self.get_queryset().filter(user=self.request.user, is_expired=False)
        if queryset.exists():
            queryset.update(is_expired=True)

        serializer.save(user=self.request.user, cert_type=self.cert_type)

    @view_config(response_serializer=CertValidRespSerializer)
    def validate(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        queryset = self.get_queryset().filter(user=request.user,
                                              is_expired=False,
                                              is_verified=False,
                                              code=serializer.validated_data.get('code'))
        if not queryset.exists():
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        instance = queryset.get()
        if timezone.now() - instance.created_date > self.expiration_delta:
            queryset.update(is_expired=True)
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        queryset.update(is_expired=True, is_verified=True)

        return Response(status=status.HTTP_200_OK)


class SMSCertViewSet(CertBaseViewSet):
    """
    list: [휴대폰 문자 인증 내역 조회]
    휴대폰 문자 인증 내역을 조회합니다.

    create: [휴대폰 문자 인증 요청]
    휴대폰 번호에 대한 문자 인증을 요청합니다. 1분이내에 5회만 요청 가능합니다.

    validate: [휴대폰 문자 인증 검증]
    인증 번호를 검증합니다. 인증 받은 번호는 다시 사용 할 수 없습니다.
    """
    serializer_class = SMSCertSerializer
    serializer_action_map = {
        'create': SMSCertCreateSerializer,
        'validate': CertValidRespSerializer
    }
    throttle_scope = 'sms_cert'


class AccountCertViewSet(CertBaseViewSet):
    """
    list: [계좌 인증 내역 조회]
    계좌 인증 내역을 조회합니다.

    create: [계좌 인증 요청]
    계좌 인증을 요청합니다. 인증은 입력받은 계좌에 1원이 이체되며, 입금내역에서 인증코드를 확인 할 수 있습니다. <br/>
    계좌 인증 요청시 기존에 인증 요청하였으나 인증 처리되지 않은 코드는 폐기됩니다.<br/>
    인증 코드는 한글 4자리로 구성되어있습니다. 예) 하하호호

    validate: [계좌 인증 검증]
    인증 코드를 검증합니다. 인증 받은 코드는 다시 사용 할 수 없습니다.

    real_name: [계좌 실명 확인]
    입력받은 계좌에 대한 실명 확인을 합니다. 실명확인시 요청하는 유저 계정에 이름(profile의 name필드)이 설정되어 있어야 합니다.
    """
    serializer_class = AccountCertSerializer
    serializer_action_map = {
        'create': AccountCertCreateSerializer,
        'validate': CertValidRespSerializer,
        'real_name': AccountRealNameSerializer,
    }

    throttle_classes_map = {
        'create': (ScopedRateThrottle,),
        'real_name': (ScopedRateThrottle,)
    }
    throttle_scope = 'account_cert'

    def perform_create(self, serializer):
        super(AccountCertViewSet, self).perform_create(serializer)
        data = ktfc_adapter.get_transfer_format(**{**serializer.data, 'code': serializer.instance.code})
        response = ktfc_adapter.request('/transfer/deposit2', data)

        if not response:
            serializer.instance.delete()
            return Response(status=status.HTTP_412_PRECONDITION_FAILED)

    def real_name(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        response = ktfc_adapter.request('/inquiry/real_name', serializer.data)

        if not response:
            return Response(status=status.HTTP_412_PRECONDITION_FAILED)

        result = json.loads(response.text) if status.is_success(response.status_code) else {}

        if result.get('account_holder_name') == self.request.user.profile.name:
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_204_NO_CONTENT)


class ARSCertViewSet(CertBaseViewSet):
    """
    create: [ARS 인증 요청]
    계좌 번호에 대한 ARS 인증을 요청합니다.

    validation: [ARS 인증 결과 확인]
    ARS에 대한 인증결과를 확인합니다.

    """
    serializer_class = ARSCertSerializer,
    serializer_action_map = {
        'create': ARSCertCreateSerializer,
        'validation': Serializer
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.order_by('-created_date').filter(user=self.request.user).values('id', 'is_verified',
                                                                                        'is_expired', 'created_date')

    def perform_create(self, serializer):
        super().perform_create(serializer)

        contract = Contract.objects.filter(user=self.request.user, is_canceled=False).get(
            id=serializer.data['contract_id'])

        data = ars_adapter.get_transfer_format(
            account_number=contract.account_number,
            birth_date=self.request.user.profile.birth_date,
            name=self.request.user.profile.name,
            phone=self.request.user.profile.phone,
            security=serializer.data['security'],
            bank_name=contract.vendor.vendor_props.company_name
        )
        try:
            ars_adapter.request_thread(data=data, auth_id=serializer.data['id'])
        except Exception as e:
            print(e)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def validation(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = queryset.first()

        if data is not None:
            if timezone.now() - data['created_date'] > self.expiration_delta:
                queryset.update(is_expired=True)
                return Response(status=status.HTTP_401_UNAUTHORIZED)

            if data['is_verified'] is True:
                return Response(status=status.HTTP_200_OK,
                                data={"message": "done"})
            elif data['is_verified'] is False and data['is_expired'] is True:
                return Response(status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response(status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION,
                                data={"message": "processing"})
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)


class OwnerCertViewSet(CertBaseViewSet):
    """
      create: [계좌 소유주 인증]
      계좌에 대한 소유주를 인증 요청 합니다.
      """
    serializer_class = OwnerCreateSerializer

    def update_auth(self, serializer):
        data = owner_adapter.get_transfer_format(
            bank_code_std=serializer.data['bank_code_std'],
            birth_date=self.request.user.profile.birth_date,
            account_number=serializer.data['account_number']
        )

        try:
            response = owner_adapter.request(data=data)
            response.encoding = response.apparent_encoding
            res_data = json.loads(response.text)

            if res_data['reply'] == '0000' and (res_data['name'] == self.request.user.profile.name):
                Auth.objects.filter(id=serializer.data['id']).update(is_verified=True)
            else:
                Auth.objects.filter(id=serializer.data['id']).update(is_verified=False, is_expired=True)
                raise NotAuthenticated("Request must be required by account owner")

            logger.info('owner auth: {auth} - {reply}, {reply_msg}, {name}'
                        .format(**(dict(res_data, **{"auth": serializer.data['id']}))))
        except Exception as e:
            logger.error(e)
            raise e

    def perform_create(self, serializer):
        super().perform_create(serializer)

        if settings.USE_REALTIME:
            self.update_auth(serializer)
        else:
            Auth.objects.filter(id=serializer.data['id']).update(is_verified=True)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AuthAccountViewSet(CertBaseViewSet):
    """
      retrieve: [계좌 인증 완료 내역 조회]
      계좌 소유주 인증 및 ars 인증이 완료된 수수료 계좌 번호와 은행 코드를 조회합니다.
      etc_2 : contract_id
    """
    serializer_class = AuthAccountSerializer
    lookup_field = 'etc_2'

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset=queryset)
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        return queryset.filter(**filter_kwargs)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user,
                                    cert_type=3,
                                    is_verified=True,
                                    is_expired=False)

    def get_object(self):
        qs = self.filter_queryset(self.get_queryset()).order_by('created_date')
        if not qs.exists():
            raise NotFound("No Account registered")
        return qs.last()
