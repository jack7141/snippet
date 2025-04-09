import logging
from collections import defaultdict
from rest_framework import viewsets, filters, status, serializers
from rest_framework.exceptions import NotAcceptable, NotFound
from rest_framework.response import Response
from rest_framework.parsers import FormParser, MultiPartParser

from drf_openapi.utils import view_config

from django.db.models import Count, Case, When, Q
from django.db.models.deletion import ProtectedError
from django.contrib.auth import get_user_model

from api.bases.contracts.choices import (
    ContractTypeChoices,
    RebalancingQueueChoices,
    ContractChoices
)
from api.bases.contracts.models import (
    ContractType,
    Contract,
    Condition,
    Extra,
    ProvisionalContract,
    Transfer,
    Term,
    RebalancingQueue,
    get_contract_status
)
from api.bases.contracts.mixins import RebalancingMixin
from api.bases.orders.models import Order
from api.versioned.v1.contracts.serializers import (
    ConditionSerializer,
    ConditionCreateSerializer,
    ContractSerializer,
    ContractCreateSerializer,
    ContractDetailSerializer,
    ContractDeletionSerializer,
    ContractCancelSerializer,
    ContractNonAssetSerializer,
    RebalancingQueueSerializer,
    RebalancingQueueReadOnlySerializer,
    ExtraSerializer,
)
from api.versioned.v1.vendors.serializers import VendorOrderSerializer
from api.versioned.v1.contracts.mixins import TerminateContractMixin

from api.versioned.v1.admin.contracts.serializers import (
    ContractIssuanceAdminSerializer,
    DProgSyncSerializer,
    RebalancingQueueAdminCreateSerializer,
    RebalancingQueueBatchSummarySerializer,
    TransferBatchSerializer,
    TermSerializer,
)

from common.viewsets import MappingViewSetMixin, AdminViewSetMixin

from .filters import (
    UserDateRangeFilter,
    ContractSearchFilter,
    ContractDeletionFilter,
    OrderDateRangeFilter,
    UserBasedContractDateRangeFilter,
    TransferFilter,
)

from .serializers import (
    UserContractSerializer,
    UserContractDashboardSerializer,
    ContractAdminCreateSerializer,
    ProvisionalSerializer
)

logger = logging.getLogger('django.server')


class ContractUserAdminViewSet(MappingViewSetMixin,
                               AdminViewSetMixin,
                               viewsets.ModelViewSet):
    """
    list:[계약 목록 조회 - 유저기준]
    유저 기준으로 계약 목록을 조회합니다.</br>
    * 검색 가능한 필드 : 계좌 번호, 계좌 종류, 유저명, 전화번호, 이메일, 출금이체 동의날짜
    * 정렬 가능한 필드
        * 'id', 'email', 'is_active', 'date_joined', 'username', 'phone', 'risk_type', 'contracts'
        * 'active_contract (계좌까지 연결된 계약 수)', 'wait_contract' (계좌 연결 준비중인 계약 수(active_contract 포함))
    * 범위 검색(UTC) : created\_at\_min, created\_at\_max  (※현재 API 페이지로는 테스트 불가능합니다. Postman등 테스트 가능)</br>
    """
    queryset = get_user_model().objects.all() \
        .select_related('profile') \
        .prefetch_related('contract_set') \
        .annotate(active_contract=Count(Case(When(contract__is_canceled=False, then=1))),
                  inactive_contract=Count(Case(When(contract__is_canceled=True, then=1)))) \
        .filter(Q(active_contract__gte=1) | Q(inactive_contract__gte=1))

    serializer_class = UserContractSerializer

    serializer_action_map = {
        'create': ContractCreateSerializer,
    }

    filter_class = UserBasedContractDateRangeFilter
    filter_backends = (filters.DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter,)
    search_fields = ('profile__name', 'profile__phone', 'email')

    ordering_fields = ('email', 'date_joined',
                       'username', 'phone', 'risk_type',
                       'contracts', 'active_contract', 'active_contract', 'inactive_contract')


class ContractDashboardViewSet(MappingViewSetMixin,
                               AdminViewSetMixin,
                               viewsets.ModelViewSet):
    """
    retrieve:[Dashboard 조회]
    유저 수, 계약 수, 계약 체결 수를 조회합니다.</br>
    범위 검색(UTC) : created\_at\_min, created\_at\_max  (※현재 API 페이지로는 테스트 불가능합니다. Postman등 테스트 가능)</br>
    users : 회원 가입일 기준 범위 </br>
    contracts : 계약 생성일 기준 범위 </br>
    orders : 주문 생성일 기준 범위
    """
    serializer_class = UserContractDashboardSerializer
    queryset = get_user_model().objects.all()
    filter_class = UserDateRangeFilter

    def retrieve(self, request, *args, **kwargs):
        data = {
            'users': self.filter_queryset(self.get_queryset()),
            'contracts': ContractSearchFilter(request.query_params, queryset=Contract.objects.all(),
                                              request=request).qs,
            'orders': OrderDateRangeFilter(request.query_params, queryset=Order.objects.all(), request=request).qs
        }
        serializer = self.get_serializer(data)
        return Response(serializer.data)


class ContractAdminViewSet(MappingViewSetMixin,
                           AdminViewSetMixin,
                           TerminateContractMixin,
                           viewsets.ModelViewSet):
    """
    retrieve:[계약 상세 조회]
    계약에 대한 상세 정보를 조회합니다.

    partial_update:[계약 업데이트]
    계약사항을 변경합니다.

    destroy:[계약 취소]
    요청한 유저의 계약을 취소합니다.</br>

    issue_context_list:[계약서명 context 조회]
    """
    queryset = Contract.objects.all().select_related('user').prefetch_related('user__profile', 'orders')

    serializer_class = ContractSerializer
    serializer_action_map = {
        'create': ContractAdminCreateSerializer,
        'simple_list': ContractNonAssetSerializer,
        'retrieve': ContractDetailSerializer,
        'destroy': ContractCancelSerializer,
        'issue_context_list': ContractIssuanceAdminSerializer,
    }

    @view_config(response_serializer=ContractSerializer)
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def simple_list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def issue_context_list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class ContractFilterAdminViewSet(ContractAdminViewSet):
    """
    list:[계약 목록 조회]
    현재 체결된 계약상태를 확인합니다.</br>
    검색 가능한 필드 : 계좌 번호, 계좌 종류, 유저명, 휴대폰번호, 이메일, 출금이체 동의날짜
    필터 가능한 필드 : 계약 생성일, 계약 상태

    계약 생성일 범위 검색(UTC) : created_at_min, created_at_max  (※현재 API 페이지로는 테스트 불가능합니다. Postman등 테스트 가능)</br>
    예1) ?created_at_min=2018-06-25                              ---> created_at >= 2018-06-25 00:00:00</br>
    예2) ?created_at_min=2018-06-25 06:00:00                     ---> created_at >= 2018-06-25 06:00:00</br>
    예3) ?created_at_max=2018-06-25                              ---> created_at <operationId= 2018-06-25 00:00:00</br>
    예4) ?created_at_min=2018-06-24&created_at_max=2018-06-25    ---> 2018-06-24<=created_at<=2018-06-25

    ***
    **결과값 Case**
    * 계약 체결 대기중 : is_active가 False
    * 현재 계약 유지중 : is_active가 True
    * 계약 취소됨 : is_canceled가 True
    ***

    create:[계약 생성]
    요청한 유저의 계약을 생성합니다.</br>
    계약 생성을 위해선 유저의 이름, 휴대폰 번호, 주소, 성향, 생년월일이 등록되어 있어야 합니다.(PUT /users/{user}/profile API로 업데이트 가능)<br/>
    유저당 생성 가능한 계약은 타입별(EA, FA) 1개이며, 현재 계약 대기상태 이거나 유지중이라면 생성되지 않습니다.

    simple_list:[계약목록 조회 - 자산정보 제외]
    자산정보를 제외한 계약 목록을 조회 합니다.</br>
    검색 가능한 필드 : 계좌 번호, 계좌 종류, 유저명, 휴대폰번호, 이메일, 출금이체 동의날짜
    필터 가능한 필드 : 계약 생성일, 계약 상태

    계약 생성일 범위 검색(UTC) : created_at_min, created_at_max  (※현재 API 페이지로는 테스트 불가능합니다. Postman등 테스트 가능)</br>
    예1) ?created_at_min=2018-06-25                              ---> created_at >= 2018-06-25 00:00:00</br>
    예2) ?created_at_min=2018-06-25 06:00:00                     ---> created_at >= 2018-06-25 06:00:00</br>
    예3) ?created_at_max=2018-06-25                              ---> created_at <operationId= 2018-06-25 00:00:00</br>
    예4) ?created_at_min=2018-06-24&created_at_max=2018-06-25    ---> 2018-06-24<=created_at<=2018-06-25

    issue_context_list:[계약서명 context 조회]

    effective_date_{min, max} 입력 시,
    주문이 있는 계약만 조회 됩니다.

    예1) ?effective_date_min=2018-06-25                          ---> orders_orders.created_at >= 2018-06-25 00:00:00</br>
    예2) ?status=1                                               ---> contracts_contract.status = '1'</br>

    필터 가능한 필드 : 계약 생성일, 계약 상태, 계약 코드, 유저, 위험성향
    """
    filter_class = ContractSearchFilter
    filter_backends = (filters.DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter,)
    search_fields = ('contract_number', 'contract_type__code', 'firm_agreement_at',
                     'user__profile__name', 'user__profile__phone', 'user__email')


class ContractDeletionAdminViewSet(MappingViewSetMixin,
                                   AdminViewSetMixin,
                                   viewsets.ModelViewSet):
    """
    list: [삭제 대상 조회]
    destroy: [계약 삭제 대상 목록 - 삭제]
    요청받은 계약 해지일 보다 작은 날짜 기준에 해당하는 계약 목록 삭제
    clean: [계약 해지 고객 정보 변경]
    요청받은 계약 해지일보다 작은 날짜 기준에 해당하는 계약에 대해, 계좌번호, 계좌대체번호, CI정보를 임의값으로 변경합니다.
    """

    CLEAN_WORD = "0000000000"
    serializer_class = ContractDeletionSerializer
    queryset = Contract.objects.filter(is_canceled=True, status=ContractChoices.STATUS.canceled) \
        .select_related('user').prefetch_related('user__profile', 'orders')
    filter_class = ContractDeletionFilter
    filter_backends = (filters.DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter,)
    search_fields = ('contract_number', 'contract_type', 'firm_agreement_at',
                     'user__profile__name', 'user__profile__phone', 'user__email')

    def get_queryset(self):
        return self.queryset.exclude(account_alias=self.CLEAN_WORD)

    def destroy(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        result = serializer.data
        queryset.delete()
        return Response(result)

    def clean(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        serializer = self.get_serializer(queryset, many=True)
        result = serializer.data

        for item in queryset:
            item.provisional.delete()

        queryset.update(account_number="0000000000", account_alias="0000000000", ci="0000000000")

        return Response(result)


class ContractNextStepViewSet(RebalancingMixin,
                              MappingViewSetMixin,
                              AdminViewSetMixin,
                              viewsets.ModelViewSet):
    """
    create: [계약-주문 자동 진행(개발용)]
    계약 ID를 이용하여 주문 처리/리밸런싱 알람등을 순차적으로 실행합니다. 정상 계약에만 적용됩니다.</br>
    <strong>개발 모드(서버 환경: DEBUG)</strong>에서만 해당 API를 이용 가능합니다.
    """
    serializer_class = serializers.Serializer
    queryset = Contract.objects.filter(is_canceled=False, status=ContractChoices.STATUS.normal)

    def get_vendor_serializer(self, *args, **kwargs):
        kwargs['context'] = self.get_serializer_context()
        return VendorOrderSerializer(*args, **kwargs)

    @view_config(response_serializer=ContractSerializer)
    def create(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = ContractSerializer(instance)
        reb_required = instance.reb_required
        temp = None

        if not instance.last_order:
            temp = self.get_vendor_serializer(data={'c_id': str(instance.id), 'mode': 'new_order'})
        elif instance.last_order and instance.last_order.status == Order.STATUS.processing:
            temp = self.get_vendor_serializer(data={'c_id': str(instance.id), 'status': Order.STATUS.completed})
        elif reb_required:
            temp = self.get_vendor_serializer(data={'c_id': str(instance.id), 'mode': instance.get_next_order_mode()})
            instance.rebalancing = False
        elif not reb_required:
            self.rebalancing_instance(instance)

        if temp and isinstance(temp, VendorOrderSerializer):
            temp.is_valid(raise_exception=True)
            temp.save()

        return Response(serializer.data)


class ProvisionalAdminViewSet(MappingViewSetMixin,
                              AdminViewSetMixin,
                              viewsets.ModelViewSet):
    """
    list:[임시 계약 목록 조회]
    * 검색 가능한 필드 : 유저명, 전화번호, 이메일
    * 정렬 가능한 필드 : 이메일(user\_\_email), 전화번호(user\_\_profile\_\_name), 생성일(created\_at), 수정일(updated\_at), 계좌별칭(account\_alias), 계약타입(contract\_type)</br>
    예1) ?ordering=-user\_\_email : 이메일 기준 내림차순 정렬</br>
    예2) ?ordering=user\_\_email : 이메일 기준 오름차순 정렬</br>
    예3) ?ordering=user\_\_profile\_\_name,-created\_at : 사용자 이름 오름차순, 생성일 내림차순 정렬</br>
    """
    serializer_class = ProvisionalSerializer
    queryset = ProvisionalContract.objects.all()
    filter_backends = (filters.OrderingFilter, filters.SearchFilter,)
    search_fields = ('user__profile__name', 'user__profile__phone', 'user__email')
    ordering_fields = ('user__email', 'user__profile__name',
                       'created_at', 'updated_at', 'account_alias', 'contract_type')


class TermAdminViewSet(MappingViewSetMixin,
                       AdminViewSetMixin,
                       viewsets.ModelViewSet):
    """
    create: [계약 조건 생성]
    list: [계약 조건 목록 조회]
    retrieve: [계약 조건 상세 조회]
    update: [계약 조건 업데이트]
    partial_update: [계약 조건 부분 업데이트]
    destroy: [계약 조건 삭제]
    삭제시 계약과 연결되어있는 상태이면 status code 406이 내려갑니다.</br>
    이 경우 연결되있는 계약과 연결을 끊은 후 삭제해야합니다.
    """

    serializer_class = TermSerializer
    queryset = Term.objects.all()
    parser_classes = (MultiPartParser, FormParser)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise NotAcceptable()


# Discretionary Progress Sync
class DProgSyncViewSet(MappingViewSetMixin,
                       AdminViewSetMixin,
                       viewsets.ModelViewSet):
    """
    create: [일임계약 해지상태 동기화]
    """
    queryset = Contract.objects \
        .filter(contract_type__operation_type=ContractTypeChoices.OPERATION_TYPE.D) \
        .exclude(status__in=[ContractChoices.STATUS.normal, ContractChoices.STATUS.canceled])

    serializer_class = DProgSyncSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ExtraAdminViewSet(MappingViewSetMixin,
                        AdminViewSetMixin,
                        viewsets.ModelViewSet):
    """
        partial_update: [계약 Extra 부분 업데이트]
    """
    serializer_class = ExtraSerializer
    queryset = Extra.objects.all()


class ConditionAdminViewSet(MappingViewSetMixin,
                            AdminViewSetMixin,
                            viewsets.ModelViewSet):
    """
        partial_update: [계약 Condition 부분 업데이트]
    """
    serializer_class = ConditionSerializer
    queryset = Condition.objects.all()

    serializer_action_map = {
        "partial_update": ConditionCreateSerializer
    }


class RebalancingQueueAdminViewSet(MappingViewSetMixin, AdminViewSetMixin, RebalancingMixin, viewsets.ModelViewSet):
    """
        batch: [대기중, 진행중인 Queue를 일괄 처리]
        * 대기중, 진행중인 Queue가 여러개인 경우, 생성일 기준 최신 Queue를 우선 처리
        * 배치 처리시점에 해당 계약이 리밸런싱 중이면, Queue를 "건너뜀" 처리함
        do_rebalancing: [계약의 대기중, 진행중인 Queue에 대해 리밸런싱 집행]
        list: [리밸런싱 Queue 목록 조회]
        create: [리밸런싱 Queue 생성]
        destroy: [계약의 대기중, 진행중인 Queue 취소 처리]
    """
    serializer_action_map = {
        'batch': RebalancingQueueReadOnlySerializer,
        'do_rebalancing': RebalancingQueueReadOnlySerializer,
        'destroy': RebalancingQueueSerializer,
        'list': RebalancingQueueSerializer,
        'create': RebalancingQueueAdminCreateSerializer,
    }
    queryset = RebalancingQueue.objects.all()
    lookup_field = 'contract_id'
    filter_fields = ('contract_id', 'status',)

    def filter_queryset(self, queryset):
        return queryset.filter(contract__status=get_contract_status(type='normal'))

    @staticmethod
    def is_rebalancing_available(contract: Contract):
        try:
            RebalancingQueueAdminCreateSerializer.validate_completed_new_order(contract=contract)
            RebalancingQueueAdminCreateSerializer.validate_rebalancing_condition(contract=contract)
        except Exception as e:
            logger.info(f"Validation error {contract}, detail: {e}")
            return False
        return True

    @view_config(response_serializer=RebalancingQueueBatchSummarySerializer)
    def batch(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(status__in=[
            RebalancingQueueChoices.STATUS.on_hold, RebalancingQueueChoices.STATUS.processing]).order_by('-created_at')
        queryset.update(status=RebalancingQueueChoices.STATUS.processing)

        results = defaultdict(int)
        canceled_queryset = self.get_queryset().filter(contract__status=get_contract_status(type='canceled'))
        if canceled_queryset.exists():
            results['canceled'] = canceled_queryset.update(status=RebalancingQueueChoices.STATUS.canceled)

        for _queue in queryset.iterator():
            if self.is_rebalancing_available(contract=_queue.contract):
                self.rebalancing_instance(_queue.contract, force_send=True)
                _queue.status = RebalancingQueueChoices.STATUS.completed
                results['completed'] += 1
                _queue.complete()
            else:
                _queue.status = RebalancingQueueChoices.STATUS.skipped
                results['skipped'] += 1
                _queue.save()
        return Response(results)

    def do_rebalancing(self, request, contract_id, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(status__in=[RebalancingQueueChoices.STATUS.on_hold, RebalancingQueueChoices.STATUS.processing])
        instance = queryset.filter(contract=contract_id).order_by('created_at').last()

        if instance is None:
            raise NotFound("No rebalancing queue for contract")

        if self.is_rebalancing_available(contract=instance.contract):
            self.rebalancing_instance(contract=instance.contract, force_send=True)
            instance.complete()
        else:
            instance.status = RebalancingQueueChoices.STATUS.skipped

        serializer = RebalancingQueueSerializer(instance)
        return Response({"result": serializer.data})

    def destroy(self, request, *args, **kwargs):
        qs = self.get_queryset().filter(status__in=[RebalancingQueueChoices.STATUS.on_hold,
                                                    RebalancingQueueChoices.STATUS.processing])
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        qs = qs.filter(**filter_kwargs)
        if not qs.exists():
            return Response(status=status.HTTP_410_GONE)

        qs.update(status=RebalancingQueueChoices.STATUS.canceled)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TransferAdminViewSet(AdminViewSetMixin,
                           viewsets.ModelViewSet):
    """
        list: [이전 계약 목록 조회]

        partial_update: [이전 상태 업데이트]
    """
    serializer_class = TransferBatchSerializer
    queryset = Transfer.objects.all()
    filter_class = TransferFilter
    filter_backends = (filters.DjangoFilterBackend, filters.OrderingFilter,)
