from datetime import datetime

from django.contrib.auth import get_user_model
from django.db.models import Count, Case, When
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from api.bases.contracts.choices import ContractTypeChoices, TransferChoices
from api.bases.contracts.adapters import account_adapter, firmbanking_adapter
from common.viewsets import MappingViewSetMixin
from common.filter_backends import MappingDjangoFilterBackend
from api.bases.users.choices import VendorPropertyChoices
from api.bases.contracts.models import (
    Contract,
    ContractType,
    Extra,
    ProvisionalContract,
    RebalancingQueue,
    Term,
    Transfer,
    TermDetail,
    get_contract_status
)
from api.versioned.v1.contracts.serializers import (
    ContractSerializer,
    ContractNonAssetSerializer,
    ContractNormalizeSerializer,
    ContractCreateSerializer,
    ContractUpdateSerializer,
    ContractDetailSerializer,
    ContractCancelSerializer,
    ContractSettlementSerializer,
    ContractAccountHistorySerializer,
    ContractCardHistorySerializer,
    ContractCardAmountSerializer,
    ContractCardOwnSerializer,
    ContractCardStatusSerializer,
    TermSerializer,
    TermDetailSerializer,
    VendorSerializer,
    VendorUserTokenSerializer,
    VendorUserTokenRespSerializer,
    VendorContractTokenSerializer,
    ProvisionalContractSerializer,
    ProvContCreateSerializer,
    UserContractSerializer,
    UserAvailableCancelContractSerializer,
    AssetChartSerializer,
    AssetAmountChartSerializer,
    ExtraSerializer,
    OrderProxyRegisterSerializer,
    OrderProxyDeleteSerializer,
    RebalancingQueueSerializer,
    RebalancingQueueCreateSerializer,
    AccountOrderStatusSerializer,
    AccountAgreeSerializer,
    KBAccountOpenStatusSerializer,
    KBThirdPartyAdvisoryReqSerializer,
    KBThirdPartyAgreementRequestSerializer,
    OCRIdentificationRequestSerializer,
    OCRIdentificationResponseSerializer,
    OCRIdentificationValidateRequestSerializer,
    KBAccountOpenAddressSearchReqSerializer,
    KBAccountOpenAddressSearchSerialReqSerializer,
    RegisterCustomerInformationRequestSerializer,
    AccountAvailablePensionDetailReqSerializer,
    AccountCertificationReqSerializer,
    AccountFromAllVendorReqSerializer,
    AccountELWDescReqSerializer,
    AccountOpenPasswordValidationReqSerializer,
    AccountOpenReqSerializer,
    AccountOwnerVerificationReqSerializer,
    AccountPensionLimitReqSerializer,
    AccountPensionDetailReqSerializer,
    AccountPensionReceiptReqSerializer,
    AccountValidationReqSerializer,
    AccountRegisterValidationReqSerializer,
    AuthIdentificationReqSerializer,
    DecryptETOEReqSerializer,
    GlobalOneMarketReqSerializer,
    TransferSerializer,
    TransferPensionReqSerializer,
    SyncStatusSerializer,
    OpenAccountStatusReqSerializer,
    SyncStatusRespSerializer,
)
from api.versioned.v1.contracts.mixins import TerminateContractMixin
from api.versioned.v1.contracts.filters import AccountHistoryFilter, CardAmountFilter, SettlementFilter
from drf_openapi.utils import view_config


class ContractViewSet(MappingViewSetMixin,
                      TerminateContractMixin,
                      viewsets.ModelViewSet):
    """
    list:[계약 목록 조회]
    현재 체결된 계약상태를 확인합니다.</br>

    | **공통** |  | **펌뱅킹** |  | **원장** |  | **협력사** |  | **reb_status.status** |  |
    |:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
    | **status** | **defs** | **status** | **defs** | **status** | **defs** | **status** | **defs** | **status** | **defs** |
    | 0 | 해지됨 | 2 | 펌뱅킹 등록중 | 22 | 해지 매도 진행중 | 4 | 협력사 해지 대기 | 1 | 지연중 |
    | 1 | 정상 유지 | 20 | 펌뱅킹 등록 실패 | 23 | 해지 매도 실패 | 41 | 협력사 계좌개설 대기 | 2 | 실패함 |
    |  |  | 21 | 펌뱅킹 등록 완료 | 24 | 해지 매도 완료 | 42 | 주문대리인 등록 대기 | 3 | 대기중 |
    |  |  | 3 | 출금이체 진행중 | 25 | 환전 진행중 | 43 | 인증토큰 발급 실패 | 4 | 진행중 |
    |  |  | 30 | 출금이체 실패 | 26 | 환전 실패 | 44 | 증권사 식별정보 조회 실패 | 5 | 완료됨 |
    |  |  | 31 | 출금이체 완료 | 27 | 환전 완료 | 45 | 전자문서 전달 실패 | 6 | 취소됨 |
    |  |  |  |  |  |  | 46 | 주문대리인 등록 실패 | 7 | 건너뜀 |
    |  |  |  |  |  |  | 47 | 주문대리인 해지중 토큰발급 실패 |  |  |
    |  |  |  |  |  |  | 48 | 주문대리인 해지 대기 |  |  |
    |  |  |  |  |  |  | 49 | 주문대리인 해지 실패 |  |  |

    retrieve:[계약 상세 조회]

    create:[계약 생성]
    요청한 유저의 계약을 생성합니다.</br>
    계약 생성을 위해선 유저의 이름, 휴대폰 번호, 주소, 성향, 생년월일이 등록되어 있어야 합니다.(PUT /users/{user}/profile API로 업데이트 가능)</br>
    유저당 생성 가능한 계약은 1개이며, 생성시 결재 여부를 확인하여 계약 상태를 활성화 하게 됩니다. </br>
    계약 생성시 별도의 계약조건을 지정하지 않는경우 현재 기본으로 적용되어있는 약관 조건으로 설정됩니다. </br>
    **기본 약관 조건 : 현재 publish 되어있고, default로 체크된 조건**

    tr_reg_date : 1, 5, 10, 15, 20, 25

    destroy:[계약 취소]
    요청한 유저의 계약을 취소합니다.</br>

    partial_update: [계약 속성 변경]
    계약의 속성을 번경합니다.

    account_history_list:[CMA 계좌 내역 조회]

    card_history_list:[카드 내역 조회]

    card_amount_list:[카드 이용/출금 가능금액 조회]

    card_isown:[카드 보유여부 조회]

    card_status:[카드 신청상태 조회]
    0: 보유없음, 1: 신청중, 2: 발급완료

    sync_status:[계약상태 sync]
    계약 id로 상태 sync 요청 시 fep로 api 확인 후 상태를 업데이트합니다.

    open_account_status:[계좌개설 완료 상태 sync]
    암호회된 데이터를 복호화한 후 완료상태에 따라 계약상태를 업데이트합니다.

    order_proxy_register:[주문대리인 등록]
    주문대리인 등록 및 일임 운용계좌로 등록합니다.</br>
    일임 계약이 아닌경우 주문대리인 등록 동작은 하지 않습니다. </br>

    오류 발생시 Response 포멧(HTTP Status Code: 412)
    ```json
    {
        "status": "계약 상태 코드",
        "message": "상태 메시지",
        "response": "통신 응답 Header 값(json)"
    }
    ```

    order_proxy_destroy:[주문대리인 해지]
    주문대리인을 해지합니다.</br>
    일임 계약이 아닌경우 주문대리인 해지 동작은 하지 않습니다. </br>
    계약 상태가 주문대리인 해지 대기(**48**), 주문대리인 해지 실패(**49**)인 경우에만 동작합니다. (계약 상태코드는 [계약 목록 조회]참조)</br>
    주문대리인 해지 성공시 계약 상태는 해지됨(**0**)으로 처리됩니다.

    오류 발생시 Response 포멧(HTTP Status Code: 412)
    ```json
    {
        "status": "계약 상태 코드",
        "message": "상태 메시지",
        "response": "통신 응답 Header 값(json)"
    }
    ```

    simple_list:[계약목록 조회 - 자산정보 제외]

    normalize_contract:[해지대기 계약 정상화]
    협력사 해지대기 상태의 계약을 정상계약으로 전환합니다. </br>
    </br>
    계약 정상화 조건 </br>
    1. 계약에 주문이 없어야함 </br>
    2. 계약의 상태가 `협력사 해지 대기(status:4)` <br>

    account_order_status:[계좌 주문상태 조회(펀드, 연금 전용)]
    요청받은 계좌의 포트폴리오 주문상태를 조회합니다.

    account_agree:[제3자 정보제공동의]
    자문계약에서만 확인이 가능 합니다.

    settlement_list:[정산 목록 조회]
    계약의 정기 수취 내역을 조회 합니다.
    """
    queryset = Contract.objects.all().select_related('user', 'vendor', 'condition', 'term', 'extra').prefetch_related(
        'user__profile')
    serializer_class = ContractSerializer
    serializer_action_map = {
        'create': ContractCreateSerializer,
        'simple_list': ContractNonAssetSerializer,
        'retrieve': ContractDetailSerializer,
        'partial_update': ContractUpdateSerializer,
        'destroy': ContractCancelSerializer,
        'normalize_contract': ContractNormalizeSerializer,
        'settlement_list': ContractSettlementSerializer,
        'account_agree': AccountAgreeSerializer,
        'account_history_list': ContractAccountHistorySerializer,
        'account_order_status': AccountOrderStatusSerializer,
        'card_history_list': ContractCardHistorySerializer,
        'card_amount_list': ContractCardAmountSerializer,
        'card_isown': ContractCardOwnSerializer,
        'card_status': ContractCardStatusSerializer,
        'order_proxy_register': OrderProxyRegisterSerializer,
        'order_proxy_destroy': OrderProxyDeleteSerializer,
        'sync_status': SyncStatusSerializer,
        'open_account_status': OpenAccountStatusReqSerializer,
    }

    filter_backends = (MappingDjangoFilterBackend,)
    filter_action_map = {
        'account_history_list': AccountHistoryFilter,
        'card_history_list': AccountHistoryFilter,
        'card_amount_list': CardAmountFilter,
        'settlement_list': SettlementFilter,
    }

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    @view_config(request_serializer=ContractCancelSerializer, response_serializer=ContractSerializer)
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def simple_list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def account_agree(self, request, *args, **kwargs):
        return self.realtime_data(request, 'api/v1/{}/account/agree', *args, **kwargs)

    def account_history_list(self, request, *args, **kwargs):
        return self.realtime_data(request, '/api/v1/{}/account/history', AccountHistoryFilter, *args, **kwargs)

    def account_order_status(self, request, *args, **kwargs):
        return self.realtime_data(request, '/api/v1/{}/account/order/status', *args, **kwargs)

    def card_history_list(self, request, *args, **kwargs):
        return self.realtime_data(request, '/api/v1/{}/card/history', AccountHistoryFilter, *args, **kwargs)

    def card_amount_list(self, request, *args, **kwargs):
        return self.realtime_data(request, '/api/v1/{}/card/amount', CardAmountFilter, *args, **kwargs)

    def card_isown(self, request, *args, **kwargs):
        return self.realtime_data(request, '/api/v1/{}/card/own', *args, **kwargs)

    def card_status(self, request, *args, **kwargs):
        return self.realtime_data(request, '/api/v1/{}/card/apply', *args, **kwargs)

    def order_proxy_register(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def settlement_list(self, request, *args, **kwargs):
        instance = self.get_object()
        type = {
            "yearly_performance": "yearly_performance_fee",
            "monthly_periodic": "monthly_periodic_fee",
        }.get('_'.join([instance.term.field_2, instance.term.field_3]), 'yearly_performance_fee')
        resp = firmbanking_adapter.get_settlement_list(account_alias=instance.account_alias, type=type)
        serializer = self.get_serializer(resp, many=True)
        return Response(serializer.data)

    @view_config(request_serializer=OrderProxyDeleteSerializer, response_serializer=OrderProxyDeleteSerializer)
    def order_proxy_destroy(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def realtime_data(self, request, endpoint, filter_class=None, *args, **kwargs):
        data = {}
        if filter_class:
            _filter = filter_class(self.request.query_params,
                                   queryset=self.get_queryset(),
                                   request=self.request)

            _filter.form.is_valid()
            data = {}
            for k, v in _filter.form.cleaned_data.items():
                if type(v) is datetime:
                    data[k] = v.strftime('%Y%m%d')
                elif v is not None:
                    data[k] = v

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        instance.get_realtime_data('realtime', endpoint.format(instance.vendor.vendor_props.code), **data)
        return Response(serializer.data)

    @view_config(request_serializer=ContractNormalizeSerializer, response_serializer=ContractSerializer)
    def normalize_contract(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def sync_status(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: SyncStatusSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def open_account_status(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer: OpenAccountStatusReqSerializer = self.get_serializer(instance=instance)
        decrypted_data = serializer.get_decrypted_data(instance, request.data)
        response_instance = serializer.change_open_account_status(instance, decrypted_data)

        response_serializer = SyncStatusRespSerializer(instance=response_instance)
        return Response(response_serializer.data)


class UserViewSet(MappingViewSetMixin,
                  viewsets.ModelViewSet):
    """
    retrieve:[계약 목록 조회]
    현재 유저의 취소되지 않은 계약 목록을 조회합니다. (status : 1)

    cancel:[계약 해지 가능 목록]
    현재 유저의 계약 해지 가능 목록을 조회합니다. (status : 31)
    출금이체까지 완료된 계약들만 나타납니다.
    """
    queryset = get_user_model().objects.all() \
        .select_related('profile') \
        .prefetch_related('contract_set', 'contract_set__orders', 'orders')
    serializer_class = UserContractSerializer

    serializer_action_map = {
        'cancel': UserAvailableCancelContractSerializer
    }

    def get_queryset(self):
        _status = get_contract_status(type='normal')

        if self.action == 'cancel':
            queryset = self.queryset.filter(id=self.request.user.id)

            if queryset.exists() and queryset.get().contract_set.get_available_cancel_contracts().count():
                return queryset
            else:
                return get_user_model().objects.none()

        else:
            return self.queryset.annotate(
                contract_conunt=Count(Case(When(contract__status=_status, then=1)))) \
                .filter(contract_conunt__gt=0, id=self.request.user.id)

    def get_object(self):
        queryset = self.get_queryset()

        try:
            return queryset.get()
        except AttributeError:
            klass__name = queryset.__name__ if isinstance(queryset, type) else queryset.__class__.__name__
            raise ValueError(
                "First argument to get_object_or_404() must be a Model, Manager, "
                "or QuerySet, not '%s'." % klass__name
            )
        except queryset.model.DoesNotExist:
            raise NotFound('No %s matches the given query.' % queryset.model._meta.object_name)

    def cancel(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class ContractAccountViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    ocr_id_card:[신분증 OCR]
    해당 계약 계약자의 신분증 OCR 결과를 반환합니다.

    retrieve_account_open_status:[계좌 개설 상태 조회]

    update_account_open_status:[계좌 개설 상태 업데이트]

    register_customer:[고객 정보 등록]

    validate_account:[비대면 본인확인 송금체크, 글로벌 원마켓, ELW 고객 위험 고지등록]

    validate_account_certification:[비대면 본인확인 송금체크]

    validate_account_elw:[ELW 고객 위험 고지등록]

    validate_account_register:[비대면 본인확인 입금 및 송금]

    validate_account_open_password:[비대면 계좌개설 조회 및 생성(비밀번호 유효성 검증)]

    validate_id_card:[신분증 OCR 검증]

    open_account:[계좌개설 및 상품개설]

    auth_identification:[H-Pin 발급]
    고객 H-Pin 번호를 발급합니다.
    고객 검증 절차를 진행하며, 고객이 아닐시 412 에러를 반환합니다.
    """
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer

    serializer_action_map = {
        "retrieve_account_open_status": KBAccountOpenStatusSerializer,
        "update_account_open_status": KBAccountOpenStatusSerializer,
        "register_customer": RegisterCustomerInformationRequestSerializer,
        "ocr_id_card": OCRIdentificationRequestSerializer,
        "validate_id_card": OCRIdentificationValidateRequestSerializer,
        "validate_account_open_password": AccountOpenPasswordValidationReqSerializer,
        "open_account": AccountOpenReqSerializer,
        "validate_account": AccountValidationReqSerializer,
        "validate_account_certification": AccountCertificationReqSerializer,
        "validate_account_register": AccountRegisterValidationReqSerializer,
        "validate_account_elw": AccountELWDescReqSerializer,
        "auth_identification": AuthIdentificationReqSerializer
    }

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def retrieve_account_open_status(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: KBAccountOpenStatusSerializer = self.get_serializer(instance=instance)
        serializer.check_account_open_rule()
        return Response(serializer.data)

    def update_account_open_status(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: KBAccountOpenStatusSerializer = self.get_serializer(instance=instance,
                                                                        data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def ocr_id_card(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: OCRIdentificationRequestSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        parsed = serializer.parse_image(instance=instance)
        response_serializer = OCRIdentificationResponseSerializer(data=parsed)
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.data)

    def validate_id_card(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: OCRIdentificationValidateRequestSerializer = self.get_serializer(instance=instance,
                                                                                     data=request.data)
        serializer.is_valid(raise_exception=True)
        res = serializer.save()
        return Response(res, status=status.HTTP_201_CREATED)

    def register_customer(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: RegisterCustomerInformationRequestSerializer = self.get_serializer(instance=instance,
                                                                                       data=request.data)
        serializer.is_valid(raise_exception=True)
        resp = serializer.save()
        return Response({}, status=status.HTTP_201_CREATED)

    def validate_account_open_password(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: AccountOpenPasswordValidationReqSerializer = self.get_serializer(instance=instance,
                                                                                     data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def open_account(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: AccountOpenReqSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        resp = serializer.data
        acct_no = (
                resp.get('entrust_acct_no', None) or
                resp.get('cma_acct_no', None) or
                resp.get('futures_options_acct_no', None) or
                resp.get('foreign_stock_exclusive_acct_no', None) or
                resp.get('isa_acct_no', None) or
                resp.get('irp_acct_no', None) or
                resp.get('pension_acct_no', None)
        )
        serializer.update_context(acct_no=acct_no)
        resp['entrust_account_no'] = acct_no
        return Response(resp, status=status.HTTP_200_OK)

    def validate_account(self, request, *args, **kwargs):
        instance = self.get_object()
        validate_serializer: AccountValidationReqSerializer = self.get_serializer(instance=instance, data=request.data)
        validate_serializer.is_valid(raise_exception=True)

        response_serializer = GlobalOneMarketReqSerializer(instance=instance, data=request.data)
        response_serializer.is_valid(raise_exception=True)

        elw_serializer = AccountELWDescReqSerializer(instance=instance, data=request.data)
        elw_serializer.is_valid(raise_exception=True)

        return Response(elw_serializer.data, status=status.HTTP_200_OK)

    def validate_account_certification(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: AccountCertificationReqSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def validate_account_register(self, request, *args, **kwargs):
        instance = self.get_object()

        validate_serializer = AccountOwnerVerificationReqSerializer(instance=instance, data=request.data)
        validate_serializer.is_valid(raise_exception=True)

        response_serializer: AccountRegisterValidationReqSerializer = self.get_serializer(instance=instance,
                                                                                          data=request.data)
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def validate_account_elw(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = AccountELWDescReqSerializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def auth_identification(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: AuthIdentificationReqSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)

        resp_serializer = DecryptETOEReqSerializer(instance=instance, data=request.data)
        resp_serializer.is_valid(raise_exception=True)

        resp = serializer.data
        serializer.update_context(resp['hpin_number'])
        return Response(serializer.data, status=status.HTTP_200_OK)


class ContractPensionViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
        list_vendor:[전 금융사 연금계좌 조회]
        전 금융사 연금계좌 조회

        retrieve_limit:[연금 변경 한도 조회]
        연금 한도 조회

        retrieve_available_limit:[설정 한도 조회]
        실시간 설정 한도 조회

        update_limit:[연금 변경 한도 설정]
        연금 한도 변경 설정

        retrieve_receipt:[연금 수익률 조회]
        """
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer

    serializer_action_map = {
        "list_vendor": AccountFromAllVendorReqSerializer,
        "update_limit": AccountPensionLimitReqSerializer,
        "retrieve_limit": AccountPensionDetailReqSerializer,
        "retrieve_receipt": AccountPensionReceiptReqSerializer,
        "retrieve_available_limit": AccountAvailablePensionDetailReqSerializer,
    }

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def list_vendor(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: AccountFromAllVendorReqSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def update_limit(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: AccountPensionLimitReqSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def retrieve_available_limit(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: AccountAvailablePensionDetailReqSerializer = self.get_serializer(instance=instance,
                                                                                     data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def retrieve_limit(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: AccountPensionDetailReqSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def retrieve_receipt(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: AccountPensionReceiptReqSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class AddressViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    search_address:[계좌 등록 주소 조회]

    search_address_serial:[계좌 등록 주소 일련번호 조회]

    """
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer

    serializer_action_map = {
        "search_address": KBAccountOpenAddressSearchReqSerializer,
        "search_address_serial": KBAccountOpenAddressSearchSerialReqSerializer,
    }

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def search_address(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: KBAccountOpenAddressSearchReqSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def search_address_serial(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: KBAccountOpenAddressSearchSerialReqSerializer = self.get_serializer(instance=instance,
                                                                                        data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class VendorViewSet(viewsets.ModelViewSet):
    """
    list:[벤더 목록 조회]
    벤더 목록을 조회합니다.
    """
    queryset = get_user_model().objects \
        .filter(is_vendor=True,
                vendor_props__isnull=False,
                vendor_props__type=VendorPropertyChoices.TYPE.investment) \
        .order_by('date_joined')
    serializer_class = VendorSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        app_version = self.request.META.get('HTTP_APP_VERSION', None)

        if app_version is not None:
            version_scheme = app_version.split('-')[0]
            major, minor, patch = version_scheme.split('.')
            if int(major) <= 2 and int(minor) < 10:
                return queryset.filter(vendor_props__code='shinhan')

        return queryset


class VendorThirdPartyViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    register_third_party_agreement:[제 3자 정보제공 동의 및 KB 유저 조회]
    해당 계약의 제 3자 정보제공 동의 후 KB 신규 회원을 구분합니다.

    register_global_onemarket:[글로벌 원마켓 등록]

    register_advisory:[투자자문계약등록]

    투자자문계약등록이 요청시 status 1) 투자자문계약 등록 대기, 2) 정상, 3) 투자자문계약 등록 실패 총 3가지 입니다.<br/>
    1) 정상 프로세스 : 투자자문계약 등록 대기 -> 정상 <br/>
    2) 실패 프로세스 : 투자자문계약 등록 대기 -> 투자자문계약 등록 실패 <br/>
    3) 실패 프로세스 : 투자자문계약 등록 대기 <br/>
    """
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer

    serializer_action_map = {
        "register_global_onemarket": GlobalOneMarketReqSerializer,
        "register_third_party_agreement": KBThirdPartyAgreementRequestSerializer,
        "register_advisory": KBThirdPartyAdvisoryReqSerializer
    }

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def register_global_onemarket(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: GlobalOneMarketReqSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def register_third_party_agreement(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: KBThirdPartyAgreementRequestSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        resp = serializer.data
        serializer.update_context(resp['secPINNumber'])
        return Response({
            'hpin_number': resp['secPINNumber']
        }, status=status.HTTP_201_CREATED)

    def register_advisory(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer: KBThirdPartyAdvisoryReqSerializer = self.get_serializer(instance=instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class VendorTokenViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    get_user_token:[벤더 토큰 생성]
    해당 벤더의 access 토큰을 발급합니다.

    get_contract_token:[벤더 encrypted data 생성]
    해당 벤더의 encrypted data를 생성합니다.
    """

    queryset = Contract.objects.all()

    serializer_action_map = {
        'get_user_token': VendorUserTokenSerializer,
        'get_contract_token': VendorContractTokenSerializer,
    }

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    @view_config(request_serializer=VendorUserTokenSerializer, response_serializer=VendorUserTokenRespSerializer)
    def get_user_token(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        endpoint = '/api/v1/{vendor_code}/token'.format(**request.data)

        res = serializer.get_realtime_data('realtime', endpoint=endpoint, **serializer.data)
        response_serializer = VendorUserTokenRespSerializer(res)
        return Response(response_serializer.data)

    def get_contract_token(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance=instance)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class ProvisionalContractViewSet(MappingViewSetMixin,
                                 viewsets.ModelViewSet):
    """
    list:[임시 계약 목록 조회]
    활성화 된 임시 계약 목록을 조회합니다.

    partial_update:[임시 계약 생성/변경]
    임시 계약 내용을 생성/변경합니다.</br>
    임시 계약은 계약 생성시 자동으로 생성됩니다. 만약 자동생성되지 않은 경우라면 추가적으로 생성 가능합니다. </br>
    임시 계약의 업데이트는 계약의 uuid 값 기준으로 업데이트 됩니다. </br>
    임시 계약과 연결된 계약이 해지상태라면 해당 임시 계약은 업데이트를 할 수 없습니다. </br>
    활성화 된 임시 계약이 있는 경우 계약 사항을 업데이트 합니다.</br>

    | step   | enc->dec |         step 처리 방식
    |:------:|:--------:|:---------------------------
    |  json  |   json   |   data 필드에 dec_data 병합
    |  json  |  string  | data 필드에 dec_data 필드로 저장
    |  none  |   json   |        data 필드에 저장
    | string |   json   |   기존값 raw_data에 저장후 병합
    |  none  |  string  |     dec_data 문자열로 병합
    | string |  string  |     dec_data 문자열로 병합


    retrieve:[임시 계약 상세 조회]
    임시 활성화 된 임시 계약 타입에 대한 상세 내역을 조회합니다.

    destroy:[임시 계약 삭제]
    현재 활성화 된 임시 계약 타입을 삭제합니다.
    """
    queryset = ProvisionalContract.objects.all()
    serializer_class = ProvisionalContractSerializer

    serializer_action_map = {
        'partial_update': ProvContCreateSerializer
    }

    lookup_field = 'contract_id'

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user, is_contract=False).order_by('-created_at')

    def perform_update(self, serializer):
        serializer.save(is_contract=False)

    def perform_destroy(self, instance):
        instance.is_contract = True
        instance.save()


class TermViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list: [계약 조건 목록 조회]
    publish 된 계약 목록을 조회합니다. 목록 조회시 기본값으로 적용되어있는 조건을 필터링 할 수 있습니다.

    retrieve: [계약 조건 상세 조회]
    """
    queryset = Term.objects.filter(is_publish=True)
    serializer_class = TermSerializer
    filter_fields = ('is_default',)


class TermDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list: [계약 상세 조건 목록 조회]
    계약 수수료 적용 가능한 목록을 조회합니다. <br/> 
    목록 조회시 기본값으로 적용되어있는 조건을 필터링 할 수 있습니다.

    retrieve: [계약 상세 조건 상세 조회]
    """
    queryset = TermDetail.objects.all()
    serializer_class = TermDetailSerializer
    filter_fields = ('is_default', 'term__contract_type')


class AssetChartViewSet(MappingViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    retrieve: [계약기준 계좌 수익률 조회]
    """
    queryset = Contract.objects.all()
    serializer_class = AssetChartSerializer

    serializer_action_map = {
        'amount': AssetAmountChartSerializer
    }

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def amount(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class ExtraViewSet(viewsets.ModelViewSet):
    """
    retrieve: [계약 추가데이터 조회]

    partial_update: [계약 추가데이터 업데이트]
    추가데이터가 없는 경우 자동 생성됩니다.
    """
    queryset = Extra.objects.all()
    serializer_class = ExtraSerializer
    lookup_field = 'contract_id'

    def get_queryset(self):
        return self.queryset.filter(contract__user=self.request.user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)

        try:
            instance = self.get_object()
        except Http404 as e:
            if Contract.objects.filter(id=self.kwargs[self.lookup_field],
                                       user=self.request.user).exists():
                instance = Extra.objects.create(contract=Contract.objects.get(id=self.kwargs[self.lookup_field]))
            else:
                raise e

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # when strategy_code is changed, forward to account server
        if instance.contract.contract_type.operation_type == ContractTypeChoices.OPERATION_TYPE.D:
            self.forward_to_account(instance)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def forward_to_account(self, instance: Extra):
        try:
            account_alias = instance.contract.account_alias
            res = account_adapter.request(f'/api/v1/accounts/{account_alias}', method='GET')
            resp = res.json()
            cur_strategy_code = resp.get('strategyCode')
            new_strategy_code = self.request.data.get('strategy_code', None)
            is_strategy_code_changed = new_strategy_code is not None and (cur_strategy_code != new_strategy_code)

            if res.status_code == 200 and is_strategy_code_changed:
                account_adapter.request(f'/api/v1/accounts/{account_alias}',
                                        method='PUT', data={'strategyCode': new_strategy_code})
        except Exception as e:
            pass
        return None


class RebalancingQueueViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    retrieve: [마지막 리밸런싱 Queue status 조회]
    list: [리밸런싱 Queue 내역 조회]
    create: [리밸런싱 Queue 생성]
    """
    queryset = RebalancingQueue.objects.all()
    serializer_action_map = {
        'retrieve': RebalancingQueueSerializer,
        'list': RebalancingQueueSerializer,
        'create': RebalancingQueueCreateSerializer
    }
    filter_fields = ('status',)
    lookup_field = 'contract_id'

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset=queryset)
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        return queryset.filter(**filter_kwargs)

    def get_queryset(self):
        return self.queryset.filter(contract__user=self.request.user)

    def list(self, request, *args, **kwargs):
        return super(RebalancingQueueViewSet, self).list(request, *args, **kwargs)

    def get_object(self):
        qs = self.filter_queryset(self.get_queryset()).order_by('created_at')
        if not qs.exists():
            raise NotFound("No Queue registered")
        return qs.last()


class TransferViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    retrieve: [마지막 계약 이전 조회]
    list: [계약 이전 내역 조회]
    create: [계약 이전 신청]
    company : 지점명이 포함된 문자열로 입력 </br>

    delete: [계약 이전 철회]
    """
    queryset = Transfer.objects.all().filter(is_canceled=False)
    serializer_action_map = {
        'create': TransferPensionReqSerializer,
        'retrieve': TransferSerializer,
    }
    filter_fields = ('status',)
    lookup_field = 'contract_id'

    def perform_destroy(self, instance):
        if instance.status in [TransferChoices.STATUS.transfer_fail,
                               TransferChoices.STATUS.transfer_auto_fail]:
            instance.is_canceled = True
            instance.status = TransferChoices.STATUS.canceled
            instance.canceled_at = timezone.now()
            instance.save()

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset=queryset)
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        return queryset.filter(**filter_kwargs)

    def perform_create(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        _contract_id = self.request.data.get('contract')
        instance = get_object_or_404(Contract.objects.filter(user=self.request.user), pk=_contract_id)
        if instance.last_transfer:
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer: TransferPensionReqSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
