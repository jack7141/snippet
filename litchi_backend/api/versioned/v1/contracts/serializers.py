import logging
import json
import requests
import pandas as pd
import datetime

from datetime import datetime as dt
from pytz import timezone as tz

from rest_framework import serializers, status, exceptions
from rest_framework.exceptions import NotFound
from rest_framework.validators import ValidationError

from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone

from dateutil import parser
from urllib.parse import urljoin, urlencode

from litchi_backend.settings import ACCOUNT_MULTIPLE_DUE_DAY
from .mixins import TerminateContractMixin

from api.bases.contracts.tasks import set_acct_nickname
from api.bases.contracts.models import (
    Assets,
    AssetsDetail,
    Contract,
    ContractType,
    Condition,
    Extra,
    ProvisionalContract,
    Rebalancing,
    RebalancingQueue,
    Term,
    Transfer,
    TermDetail,
    ContractStatus,
    get_contract_status
)
from api.bases.orders.models import Order
from api.bases.contracts.adapters import account_adapter
from api.bases.funds.utils import BDay
from api.bases.users.models import Profile, User

from common.algorithms.seed_cbc import SeedCBC
from common.algorithms.aes import Aes
from common.exceptions import PreconditionFailed, PreconditionRequired, ConflictException
from common.pdf_generator.contract_doc_generator import ContractPDFRendererFactory
from common.utils import DotDict

from api.bases.contracts.choices import (
    ContractChoices,
    ContractTypeChoices,
    RebalancingQueueChoices,
    ProvisionalContractChoices,
    AccountStatusChoices
)

SEED_IV = settings.SEED_IV
FEP_API_BACKEND = settings.FEP_API_BACKEND
AES_KEY = DotDict(settings.AES_KEY)

logger = logging.getLogger('django.server')


class RebalancingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rebalancing
        fields = ('created_at', 'sold_at', 'bought_at',)


class RebalancingQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = RebalancingQueue
        fields = '__all__'
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: '조건에 만족하는 Queue가 존재하지 않음',
        }


class RebalancingQueueReadOnlySerializer(serializers.ModelSerializer):
    class Meta:
        model = RebalancingQueue
        fields = ('id', 'status', 'created_at', 'updated_at', 'completed_at',)
        extra_kwargs = {
            "status": {'read_only': True, },
            "completed_at": {'read_only': True, }
        }


class RebalancingQueueCreateSerializer(serializers.ModelSerializer):
    status = serializers.HiddenField(default=RebalancingQueueChoices.STATUS.on_hold, help_text="진행상태")

    class Meta:
        model = RebalancingQueue
        fields = ('id', 'contract', 'status', 'created_at', 'updated_at',)
        extra_kwargs = {
            'contract': {'write_only': True, }
        }
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: "해당 사용자의 계약을 찾을 수 없음",
            status.HTTP_409_CONFLICT: "이미 등록된 Rebalancing Queue 존재",
            status.HTTP_428_PRECONDITION_REQUIRED: 'Queue 생성 조건을 만족하지 않음',
        }

    def validate_contract(self, contract):
        if contract.contract_type.code not in ['EA', 'FA', 'KBPA']:
            # Todo contract_type 조건 변경처리 필
            raise ValidationError("ContractType must be KR FUND or KR ETF")

        if contract.status.code not in [get_contract_status(type='normal', code=True)]:
            raise PreconditionRequired("Contract status must be normal")

        self.validate_user(user=contract.user)
        self.validate_completed_new_order(contract=contract)
        self.validate_rebalancing_condition(contract=contract)

        rebalancing_queues = RebalancingQueue.objects.filter(contract=contract,
                                                             status__in=[RebalancingQueueChoices.STATUS.on_hold,
                                                                         RebalancingQueueChoices.STATUS.processing])
        if rebalancing_queues.exists():
            raise ConflictException("Contract already has queued rebalancing request")
        return contract

    def validate_user(self, user):
        if self.context['request'].user != user:
            raise NotFound("Contract could not found")

    @staticmethod
    def validate_completed_new_order(contract):
        queryset = contract.orders.filter(mode=Order.MODES.new_order, status=Order.STATUS.completed)
        if not queryset.exists():
            raise PreconditionRequired("New order must be completed")

        queryset_in_24h = queryset.filter(completed_at__lte=timezone.now() - datetime.timedelta(hours=24))
        if not queryset_in_24h.exists():
            raise PreconditionRequired("New orders must pass 24 hours after completed")
        return True

    @staticmethod
    def validate_rebalancing_condition(contract: Contract):
        if contract.rebalancing:
            raise PreconditionRequired("Rebalancing flag is already activated")

        if contract.rebs.exists():
            last_reb = contract.rebs.latest('created_at')

            if last_reb.sold_at and last_reb.bought_at:
                if last_reb.bought_at <= timezone.now() - datetime.timedelta(hours=24):
                    return True
                else:
                    raise PreconditionRequired("last rebalancing must pass 24 hours after completed")
            else:
                raise PreconditionRequired("Has rebalancing in progress")
        return True


class TermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = '__all__'


class TermDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TermDetail
        fields = '__all__'


class TransferPensionRespSerializer(serializers.ModelSerializer):
    # 연금온라인이전신청
    class TransferPensionRespDataSerializer(serializers.Serializer):
        output_len = serializers.CharField(help_text="", required=False)
        output_classification = serializers.CharField(help_text="", required=False)
        output_msg = serializers.CharField(help_text="", required=False)

    dataBody = TransferPensionRespDataSerializer(required=False)


class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        fields = '__all__'


class TransferPensionReqSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    opponent_acct_no = serializers.CharField(source='account_number', write_only=True, help_text="상대계좌번호")
    opponent_org_name = serializers.CharField(source='vendor', write_only=True, help_text="상대기관명")
    opponent_company = serializers.CharField(source='company',
                                             write_only=True, required=False, help_text="상대기관명")
    opponent_company_code = serializers.CharField(source='company_code', write_only=True, required=False,
                                                  help_text="상대기관명")

    class Meta:
        model = Transfer
        extra_kwargs = {
            'contract': {'write_only': True, }
        }
        error_status_codes = {
            status.HTTP_409_CONFLICT: '연금 이전 신청이 이미 존재함',
        }
        fields = (
            'contract', 'user', 'opponent_acct_no', 'opponent_org_name', 'opponent_company', 'opponent_company_code',
            'product_type', 'id')

    def is_valid(self, raise_exception=False):
        super().is_valid(raise_exception=raise_exception)

        instance = self.validated_data.get('contract')
        user = self.validated_data.get('user')

        endpoint = "/api/v1/kb/account/pension/transfer"
        self.initial_data['opponent_acct_name'] = user.profile.name
        response = instance.get_realtime_data('realtime', endpoint, **self.initial_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        self.validated_data.pop('user')
        return True

    def create(self, validated_data):
        return super().create(validated_data)


class TransferCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        fields = '__all__'
        extra_kwargs = {
            'contract': {'write_only': True, }
        }
        error_status_codes = {
            status.HTTP_428_PRECONDITION_REQUIRED: '계약 이전 조건을 만족하지 않음',
        }

    def create(self, validated_data):
        return super().create(validated_data)


class ConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Condition
        exclude = ('volume_path', 'doc_path')
        extra_kwargs = {
            'sign': {'write_only': True, },
        }


class ConditionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Condition
        exclude = ('contract', 'volume_path', 'doc_path', 'created_at', 'updated_at')
        extra_kwargs = {
            'sign': {'write_only': True, },
        }

    def validate(self, attrs):
        if not hasattr(self.instance, "contract"):
            return attrs

        if self.instance.contract.contract_type.is_orderable and \
                self.instance.contract.contract_type.operation_type == ContractTypeChoices.OPERATION_TYPE.A:
            if attrs.get('set_limit') is not None:
                update_amt = attrs.get("set_limit")
                endpoint = 'api/v1/kb/account/pension/limit'
                data = {
                    'update_amt': update_amt
                }
                response = self.instance.contract.get_realtime_data('realtime', endpoint, **data)

                if not response:
                    raise PreconditionFailed(self.instance.contract.realtime)

        return attrs


class ExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Extra
        fields = ('label', 'target_date', 'catalog_id', 'strategy_code')
        error_status_codes = {
            status.HTTP_400_BAD_REQUEST: None,
            status.HTTP_404_NOT_FOUND: None
        }


class TRAccountDividendDataSerializer(serializers.Serializer):
    pretax_dividend_amt = serializers.FloatField(help_text="세전 배당금(USD)")
    tax_amt = serializers.FloatField(help_text="배당금 소득세(USD)")
    dividend_amt = serializers.FloatField(help_text="세후 배당금(USD)")


class AssetSerializer(serializers.ModelSerializer):
    evaluation_amount = serializers.SerializerMethodField(read_only=True, help_text='평가금액')
    gross_loss = serializers.SerializerMethodField(read_only=True, help_text='평가손익')
    return_rate = serializers.SerializerMethodField(read_only=True, help_text='평가손익률')
    dividend = serializers.SerializerMethodField(allow_null=True, help_text="배당금 관련", default=None)

    class Meta:
        model = Assets
        fields = ('base', 'deposit', 'evaluation_amount', 'gross_loss', 'return_rate', 'dividend', 'created_at',)

    def get_evaluation_amount(self, obj):
        return obj.balance + obj.deposit

    def get_gross_loss(self, obj):
        return (obj.balance + obj.deposit) - obj.base

    def get_return_rate(self, obj):
        try:
            return round((((obj.balance + obj.deposit) / obj.base) - 1) * 100, 2)
        except ZeroDivisionError:
            return None

    def get_dividend(self, obj):
        # TODO 실시간 데이터 미제공인 경우에 배당금 처리 추가 작업 필요
        return None


class AssetRealtimeSerializer(serializers.Serializer):
    base = serializers.FloatField(source='invt_bsamt', help_text='투자원금')
    deposit = serializers.FloatField(source='new_invt_amt', help_text='예수금')
    evaluation_amount = serializers.FloatField(source='tot_evlt_amt', help_text='평가금액')
    gross_loss = serializers.FloatField(source='reve_amt', help_text='평가손익')
    return_rate = serializers.FloatField(source='reve_rt', help_text='평가손익률')
    dividend = TRAccountDividendDataSerializer(allow_null=True, help_text="배당금 관련", default=None)
    created_at = serializers.SerializerMethodField(help_text='조회일시')

    def get_created_at(self, obj):
        return timezone.now()


class AssetDetailSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='asset.name', help_text='자산명')
    asset_category = serializers.CharField(source='asset.get_asset_category', help_text='자산군')
    gross_loss = serializers.SerializerMethodField(read_only=True, help_text='수익금')
    return_rate = serializers.SerializerMethodField(read_only=True, help_text='수익률')

    class Meta:
        model = AssetsDetail
        fields = ('code', 'buy_price', 'shares', 'balance', 'name', 'asset_category',
                  'gross_loss', 'return_rate', 'created_at')

    def get_gross_loss(self, obj):
        return obj.balance - obj.buy_price

    def get_return_rate(self, obj):
        try:
            return round(((obj.balance / obj.buy_price) - 1) * 100, 2)
        except ZeroDivisionError:
            return None


class AssetDetailRealtimeSerializer(serializers.Serializer):
    code = serializers.CharField(source='inves_soct_fund_code', help_text='자산코드')
    name = serializers.CharField(source='asset.name', help_text='자산명')
    asset_category = serializers.CharField(source='asset.get_asset_category', help_text='자산군')

    buy_price = serializers.FloatField(source='invt_bsamt', help_text='투자원금')
    balance = serializers.FloatField(source='evlt_amt', help_text='평가금액')
    gross_loss = serializers.FloatField(source='reve_amt', help_text='수익금')
    return_rate = serializers.FloatField(source='reve_rt', read_only=True, help_text='수익률')
    created_at = serializers.SerializerMethodField(help_text='조회일시')

    def get_created_at(self, obj):
        return timezone.now()


def asset_serializer_factory(detail=False, *args, **kwargs):
    if settings.USE_REALTIME:
        if detail:
            serializer_class = AssetDetailRealtimeSerializer
        else:
            serializer_class = AssetRealtimeSerializer
    else:
        if detail:
            serializer_class = AssetDetailSerializer
        else:
            serializer_class = AssetSerializer

    return serializer_class(**kwargs)


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('id', 'mode', 'created_at', 'updated_at', 'completed_at', 'order_rep', 'status')


class ContractNonAssetSerializer(serializers.ModelSerializer):
    term = TermSerializer(read_only=True)
    email = serializers.StringRelatedField(source='user', help_text='이메일')
    username = serializers.CharField(source='user.profile.name', read_only=True, help_text='유저명')
    phone = serializers.CharField(source='user.profile.phone', read_only=True, help_text='전화번호')
    reb_required = serializers.BooleanField(read_only=True, help_text='리밸런싱 여부')
    reb_status = serializers.JSONField(read_only=True, help_text='리밸런싱 상태')
    next_rebalancing = serializers.DateTimeField()
    condition = ConditionSerializer(required=False)
    extra = ExtraSerializer(required=False)
    last_transfer = TransferSerializer(required=False)
    last_reb = RebalancingSerializer(required=False)
    last_order = OrderSerializer(required=False)

    class Meta:
        model = Contract
        exclude = ('user',)
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }


class RestrictTimeContractSerializer(ContractNonAssetSerializer):
    asset = AssetSerializer(source='get_stored_asset', read_only=True)


class ContractSerializer(ContractNonAssetSerializer):
    asset = asset_serializer_factory(detail=False, source='get_latest_asset_with_update', read_only=True,
                                     help_text='최신 평가 정보(15분 주기 업데이트)')

    def to_representation(self, instance):
        # Note: 실시간 데이터 오류있는 시간 방어 코드
        if instance.vendor.vendor_props.is_restrict():
            return RestrictTimeContractSerializer().to_representation(instance)
        return super().to_representation(instance)


class ContractNormalizeSerializer(ContractNonAssetSerializer):
    class Meta:
        model = Contract
        fields = []
        acceptable_status = [ContractChoices.STATUS.vendor_wait_cancel]

    def is_valid(self, raise_exception=False):
        if super(ContractNormalizeSerializer, self).is_valid(raise_exception=raise_exception):
            if self.instance:
                if self.instance.status.code not in self.Meta.acceptable_status:
                    acceptable_status_names = [ContractStatus.objects.get(code=i).name for i in
                                               self.Meta.acceptable_status]
                    raise PreconditionFailed(
                        detail=f"contract_status({ContractStatus.objects.get(code=self.instance.status.code).name})"
                               f" must be in {acceptable_status_names}")
                elif self.instance.orders.all().exists():
                    raise PreconditionFailed(detail=f"Contract has order history")
            else:
                raise ValidationError(detail="instance must be defined")
            return True
        return False

    def save(self, **kwargs):
        self.instance.status = get_contract_status(type='normal')
        return super().save(**kwargs)

    def to_representation(self, instance):
        serializer = ContractSerializer(instance=instance)
        return serializer.data


class ContractUpdateSerializer(ContractSerializer):
    condition = ConditionCreateSerializer(required=False)

    class Meta:
        model = Contract
        fields = ('risk_type', 'account_alias', 'account_number', 'status', 'condition')

        extra_kwargs = {
            'status': {'read_only': True},
        }

        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
            status.HTTP_412_PRECONDITION_FAILED: "계좌번호/대체번호가 할당된 상태에서 변경 요청시 발생"
        }

    def is_valid(self, raise_exception=False):
        if super().is_valid(raise_exception=raise_exception):
            keys = list(self.validated_data.keys())
            couple = ['account_alias', 'account_number']

            if all(i in keys for i in couple):
                instance = self.instance
                changeable = (instance.contract_number == instance.account_alias == instance.account_number)

                if not changeable:
                    if raise_exception:
                        raise PreconditionFailed()
                    else:
                        return False
            return True
        return False

    def update(self, instance, validated_data):
        condition = validated_data.get('condition')
        risk_type = validated_data.get('risk_type')

        if condition:
            del validated_data['condition']

            if hasattr(instance, 'condition'):
                condition_serializer = ConditionCreateSerializer(instance.condition, data=condition, partial=True)
                condition_serializer.is_valid(raise_exception=True)
                condition_serializer.save()
            else:
                Condition.objects.create(**dict({'contract': instance, **condition}))

        if risk_type:
            account_adapter.update_risk_type(instance.account_alias, risk_type)

        return super().update(instance, validated_data)


# Note: 실시간 데이터 오류시간 보완용
class RestrictTimeDetailSerializer(ContractNonAssetSerializer):
    birth_date = serializers.DateField(source='user.profile.birth_date', help_text='생년월일')
    gender_code = serializers.IntegerField(source='user.profile.gender_code', help_text='주민번호 7번째 자리')
    condition = ConditionSerializer(help_text='계약 조건')
    asset = AssetSerializer(source='get_stored_asset', read_only=True)
    asset_details = AssetDetailSerializer(many=True, source='get_stored_asset_details', read_only=True)
    next_rebalancing = serializers.DateTimeField()
    rebalancing = RebalancingSerializer(many=True, source='rebs')


class ContractDetailSerializer(ContractNonAssetSerializer):
    birth_date = serializers.DateField(source='user.profile.birth_date', help_text='생년월일')
    gender_code = serializers.IntegerField(source='user.profile.gender_code', help_text='주민번호 7번째 자리')
    condition = ConditionSerializer(help_text='계약 조건')
    asset = asset_serializer_factory(detail=False, source='get_latest_asset', read_only=True, help_text='실시간 평가 정보')
    asset_details = asset_serializer_factory(detail=True, many=True, source='get_assets', read_only=True)
    next_rebalancing = serializers.DateTimeField()
    rebalancing = RebalancingSerializer(many=True, source='rebs')

    def to_representation(self, instance):
        # Note: 실시간 데이터 오류있는 시간 방어 코드
        if instance.vendor.vendor_props.is_restrict():
            return RestrictTimeDetailSerializer().to_representation(instance)
        return super().to_representation(instance)


class ContractSettlementSerializer(serializers.Serializer):
    class ContractWithdrawlSerailizer(serializers.Serializer):
        id = serializers.IntegerField()
        mode = serializers.CharField()
        status = serializers.IntegerField(help_text='출금 상태')
        expired_count = serializers.IntegerField()
        expired_at = serializers.DateTimeField()
        created_at = serializers.DateTimeField()
        updated_at = serializers.DateTimeField()
        settlement = serializers.IntegerField()

    id = serializers.IntegerField()
    previous_base_ymd = serializers.DateTimeField(help_text="시작일")
    base_ymd = serializers.DateTimeField(help_text="정산일자")
    realized_evaluated_amount = serializers.IntegerField(help_text="평가금액(수취내역 반영)")
    calculated_at = serializers.DateTimeField(help_text='종료일')
    base_amount = serializers.IntegerField(help_text="투자원금")
    evaluated_amount = serializers.IntegerField(help_text="평가금액(수 미반영)")
    realized_profit = serializers.IntegerField(help_text="수익금")
    is_last = serializers.BooleanField(help_text="마지막여부")
    fees = serializers.IntegerField(help_text="수수료")
    created_at = serializers.DateTimeField(help_text="생성일")
    updated_at = serializers.DateTimeField(help_text="수정일")
    status = serializers.IntegerField(help_text="정산서 상태")
    type = serializers.CharField(help_text="정산 타입")
    is_free = serializers.BooleanField(help_text="무료 정산 유무")
    withdrawals = ContractWithdrawlSerailizer(many=True, help_text="출금 내역")


class AccountHistorySerializer(serializers.Serializer):
    askmn_name = serializers.CharField(help_text='입금자명', source='npsb_rcpt_askmn_nm')
    rmrk_code = serializers.CharField(help_text='영업적요코드', source='bsns_rmrk_code')
    rmrk_name = serializers.CharField(help_text='적요명', source='rmrk_nm')
    amount = serializers.IntegerField(help_text='현금 금액', source='cash_amt')
    total_deposit = serializers.IntegerField(help_text='총예수금', source='tdpos')
    deal = serializers.SerializerMethodField(help_text='거래일자')

    def get_deal(self, instance):
        return parser.parse(
            f"{instance.get('deal_ymd')} {instance.get('deal_ttm_exp')} {timezone.localtime().tzname()}")


class AccountOrderStatusRowSerializer(serializers.Serializer):
    fund_code = serializers.CharField(help_text="펀드 코드")
    stbd_code = serializers.CharField(help_text="종목 코드(투신협회펀드코드)")
    stbd_nm = serializers.CharField(help_text="종목명")
    order_date = serializers.CharField(help_text="주문 일자")
    execution_date = serializers.CharField(help_text="체결 일자")
    settlement_date = serializers.CharField(help_text="결제 일자")


class AccountOrderStatusSerializer(serializers.Serializer):
    """
    {
        "is_completed": "Y",
        "list": [
            {
                "fund_code": "2074605",
                "stbd_code": "K55364B65695",
                "stbd_nm": "에셋플러스글로벌리치투게더증권자투자1[주식](Ce)",
                "order_date": "20220216",
                "execution_date": "20220221",
                "settlement_date": "20220228"
            },
            {
                "fund_code": "0000000",
                "stbd_code": "000000000000",
                "stbd_nm": "유동성",
                "order_date": "",
                "execution_date": "",
                "settlement_date": ""
            }
        ]
    }
    """
    is_completed = serializers.CharField(source='realtime.is_completed', read_only=True)
    list = AccountOrderStatusRowSerializer(many=True, source='realtime.list', read_only=True)


class AccountAgreeSerializer(serializers.Serializer):
    """
    {
        "agree_yn": "Y",
        "third_party_info_offer_consent_date": "20220228",
        "expire_date": "20220221",
    }
    """
    agree_yn = serializers.CharField(source='realtime.agree_yn', read_only=True)
    third_party_info_offer_consent_date = serializers.CharField(source='realtime.third_party_info_offer_consent_date',
                                                                read_only=True)
    expire_date = serializers.CharField(source='realtime.expire_date', read_only=True)


class CardHistoryItemSerializer(serializers.Serializer):
    askmn_name = serializers.CharField(help_text='통장 출력내용', source='psb_oprt_cntt')
    rmrk_name = serializers.CharField(help_text='적요명', source='rmrk')
    amount = serializers.IntegerField(help_text='승인 금액', source='acce_amt')
    deal = serializers.SerializerMethodField(help_text='거래일자')

    def get_deal(self, instance):
        return parser.parse(
            f"{instance.get('acct_ymd')} {instance.get('deal_ttm_exp')} {timezone.localtime().tzname()}")


class ContractHistoryBaseSerializer(serializers.ModelSerializer):
    repeat_key = serializers.CharField(source='realtime.repeat_key', read_only=True)
    histories = serializers.ListField(read_only=True)

    class Meta:
        model = Contract
        fields = ('histories', 'repeat_key')


class ContractAccountHistorySerializer(ContractHistoryBaseSerializer):
    histories = AccountHistorySerializer(many=True, source='realtime.list', read_only=True)


class ContractCardHistorySerializer(ContractHistoryBaseSerializer):
    total_approved_amount = serializers.FloatField(source='realtime.tot_acce_amt', read_only=True, help_text='총 승인금액')
    histories = CardHistoryItemSerializer(many=True, source='realtime.list', read_only=True)

    class Meta:
        model = Contract
        fields = ('histories', 'repeat_key', 'total_approved_amount')


class ContractCardAmountSerializer(serializers.ModelSerializer):
    available_amount = serializers.IntegerField(source='realtime.outm_aval_amt', read_only=True, help_text='출금가능금액')
    used_amount = serializers.IntegerField(source='realtime.card_use_amt', read_only=True,
                                           help_text='카드사용금액(입력받은 월 기준 카드 사용금액 총합')

    class Meta:
        model = Contract
        fields = ('available_amount', 'used_amount')


class ContractCardOwnSerializer(serializers.ModelSerializer):
    is_own = serializers.BooleanField(source='realtime.hold_yn', read_only=True, help_text='보유여부(true:보유, false:미보유)')

    class Meta:
        model = Contract
        fields = ('is_own',)


class ContractCardStatusSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(source='realtime.stat_tp_code', read_only=True,
                                     choices=[(0, '보유없음'), (1, '신청중'), (2, '발급완료')])

    class Meta:
        model = Contract
        fields = ('status',)


class ContractCancelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ('cancel_reason',)


class ContractDeletionSerializer(serializers.ModelSerializer):
    email = serializers.StringRelatedField(source='user', help_text='이메일')
    orders = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    provisional = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Contract
        fields = ('id', 'contract_number', 'contract_type',
                  'account_alias', 'account_number',
                  'is_canceled', 'status', 'email', 'orders',
                  'provisional')


class ProfileValidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('name', 'phone', 'address', 'birth_date', 'risk_type')
        extra_kwargs = {
            'name': {'required': True, 'allow_null': False},
            'phone': {'required': True, 'allow_null': False},
            'birth_date': {'required': True, 'allow_null': False},
            'risk_type': {'required': True, 'allow_null': False}
        }


class VendorSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='profile.name')
    code = serializers.CharField(source='vendor_props.code')

    class Meta:
        model = get_user_model()
        fields = ('id', 'name', 'code',)


class VendorUserTokenRespSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="Access 토큰")


class VendorUserTokenSerializer(serializers.Serializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    vendor_code = serializers.CharField(help_text="vendor 구분")

    def get_realtime_data(self, field_name, endpoint, method="POST", *args, **kwargs):
        setattr(self, field_name, None)

        headers = {'Content-Type': "application/json"}
        url = urljoin(FEP_API_BACKEND, endpoint)
        response = requests.request(method, url, headers=headers, json={**kwargs})

        if not response:
            try:
                setattr(self, field_name, response.json())
            except:
                pass
            return None

        ret = response.json()
        body = ret.get('dataBody')

        if body is not None:
            ret.update({k: v.strip() if type(v) == str else v for k, v in body.items()})

        setattr(self, field_name, ret)
        return ret

    def to_representation(self, instance):
        representation = super(VendorUserTokenSerializer, self).to_representation(instance)
        representation['ci_valu'] = self.validated_data['user'].profile.ci
        representation['name'] = self.validated_data['user'].profile.name
        representation['birth'] = self.validated_data['user'].profile.birth_date.strftime('%Y%m%d')
        representation['phone'] = self.validated_data['user'].profile.phone
        return representation


class VendorContractTokenSerializer(serializers.Serializer):
    data = serializers.SerializerMethodField(help_text="암호화 데이터", read_only=True)

    def is_valid(self, raise_exception=False):
        if self.instance.status.code not in [
            get_contract_status(type='vendor_wait_account', code=True),
            get_contract_status(type='vendor_contract_transaction_limit_wait', code=True),
            get_contract_status(type='fractional_share_trading_waiting', code=True),
            get_contract_status(type='KRW_margin_apply_wait', code=True)
        ]:
            raise PreconditionFailed(detail="The contract status has no data to encrypt.")

    def get_hanaw_encrypted_data(self, instance: Contract):
        if instance.status.code in [
            get_contract_status(type='vendor_wait_account', code=True)
        ]:
            encrypted_data = '{}|{}|{}|{}|{}|{}'.format(
                instance.user.profile.name,
                instance.user.profile.birth_date.strftime('%y%m%d'),
                instance.user.profile.mobile_carrier.lstrip('0') if instance.user.profile.mobile_carrier else '1',
                instance.user.profile.phone.replace('-', ''),
                dt.now(tz('Asia/Seoul')).strftime('%Y%m%d%H%M%S'),
                instance.pk
            )

        if instance.status.code in [
            get_contract_status(type='vendor_contract_transaction_limit_wait', code=True),
            get_contract_status(type='fractional_share_trading_waiting', code=True),
            get_contract_status(type='KRW_margin_apply_wait', code=True)
        ]:
            encrypted_data = '{}|{}|{}|{}|{}'.format(
                instance.user.profile.ci,
                instance.account_alias[:len(instance.account_alias) - 3],
                instance.account_number[:len(instance.account_number) - 3],
                dt.now(tz('Asia/Seoul')).strftime('%Y%m%d%H%M%S'),
                instance.pk
            )

        return encrypted_data

    def get_data(self, obj):
        func = getattr(self, 'get_{}_encrypted_data'.format(obj.vendor.vendor_props.code))
        key = AES_KEY.get(obj.vendor.vendor_props.code.upper()).encode()
        encryptor = Aes(key)
        return urlencode({'param': encryptor.encrypt(func(obj))})[6:]


class ProvisionalContractSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = ProvisionalContract
        fields = ('user', 'account_alias', 'contract_type', 'email', 'step', 'contract')
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }


class ProvContCreateSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    enc_data = serializers.CharField(max_length=4000, required=False, help_text='암호화 문자열')

    class Meta:
        model = ProvisionalContract
        fields = ('user', 'account_alias', 'contract_type', 'step', 'enc_data')
        error_status_codes = {
            status.HTTP_400_BAD_REQUEST: None,
        }
        extra_kwargs = {
            'contract_type': {'read_only': True},
            'contract': {'read_only': True}
        }

    def is_valid(self, raise_exception=False):
        if super().is_valid(raise_exception=raise_exception):
            account_alias = str(self.validated_data.get('account_alias')).lower()
            if account_alias == 'undefined':
                raise ValidationError(detail={'account_alias': ['This field must be not "undefiend" string.']})

            return True
        return False

    @staticmethod
    def is_valid_json(data, update=True):
        try:
            data = json.loads(data)
            if update and data.get('name', None) and not data.get('username', None):
                data.update({"username": data.get('name')})
        except Exception as e:
            return False, data
        return True, data

    def enc_to_step(self, validated_data, instance=None):
        enc_data = validated_data.get('enc_data')

        if enc_data:
            """
            | step   | enc->dec |         step 처리 방식
            |:------:|:--------:|:---------------------------
            |  json  |   json   |   data 필드에 dec_data 병합
            |  json  |  string  | data 필드에 dec_data 필드로 저장
            |  none  |   json   |        data 필드에 저장
            | string |   json   |   기존값 raw_data에 저장후 병합
            |  none  |  string  |     dec_data 문자열로 병합
            | string |  string  |     dec_data 문자열로 병합
            """
            if instance:
                step = validated_data.get('step', instance.step or '')
                decryptor = SeedCBC(validated_data.get('account_alias', instance.account_alias), SEED_IV)
            else:
                step = validated_data.get('step', '')
                decryptor = SeedCBC(validated_data.get('account_alias'), SEED_IV)

            try:
                dec_data = decryptor.decrypt(enc_data)
            except Exception as e:
                raise exceptions.ValidationError({'enc_data': 'decrypt failed.'})

            b_step, step = self.is_valid_json(step, update=False)
            b_dec, dec_data = self.is_valid_json(dec_data)

            if b_step:
                if b_dec:
                    step['data'].update(dec_data) if step.get('data') else step.update({'data': dec_data})
                else:
                    temp = {'dec_data': dec_data}
                    step['data'].update(temp) if step.get('data') else step.update({'data': temp})
                step = json.dumps(step)
            else:
                if b_dec and not step:
                    step = json.dumps({'data': dec_data})
                elif b_dec and step:
                    step = json.dumps({
                        'raw_data': step,
                        'data': dec_data
                    })
                else:
                    step += dec_data

            validated_data.update({'step': step})
            del validated_data['enc_data']
        return validated_data

    def create(self, validated_data):
        self.enc_to_step(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self.enc_to_step(validated_data, instance=instance)
        return super().update(instance, validated_data)


class VendorDefault(object):
    requires_context = True

    def set_context(self, serializer_field):
        try:
            data = serializer_field.context['request'].data
            # Note: App에서 Vendor 없이 정보 계약만 미리 생성하는 경우가 있어 아래 코드를 적용함.
            if data.get('contract_type') in ContractType.objects.filter(is_orderable=False).values_list('code',
                                                                                                        flat=True):
                self.vendor = User.objects.get(vendor_props__code='shinhan')
            elif data.get('contract_type') in ContractType.objects.filter(is_orderable=True).values_list('code',
                                                                                                         flat=True):
                self.vendor = User.objects.get(vendor_props__code='kb')
        except:
            pass

    def __call__(self):
        return self.vendor


class TermDefault(object):
    requires_context = True

    def set_context(self, serializer_field):
        data = serializer_field.context['request'].data
        try:
            self.term = Term.objects.filter(contract_type=data.get('contract_type')).get(is_default=True,
                                                                                         is_publish=True)
        except Term.DoesNotExist:
            self.term = Term.objects.filter(contract_type=None).get(is_default=True, is_publish=True)

    def __call__(self):
        return self.term


class TermDetailDefault(object):
    requires_context = True

    def set_context(self, serializer_field):
        data = serializer_field.context['request'].data
        self.term_detail = TermDetail.objects.get_term_detail(
            contract_type=data.get('contract_type'),
            pk=data.get('term_detail'))

    def __call__(self):
        return self.term_detail


class ContractStatusDefault(object):

    def set_context(self, serializer_field):
        try:
            self.status = ContractStatus.objects.get(type='vendor_wait_account')
        except:
            self.status = ContractChoices.STATUS.vendor_wait_account

    def __call__(self):
        return self.status


class ContractCreateSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    is_canceled = serializers.HiddenField(default=False)
    term = serializers.PrimaryKeyRelatedField(queryset=Term.objects.all(),
                                              default=TermDefault(),
                                              required=False, allow_null=False)
    condition = ConditionCreateSerializer(required=False)
    extra = ExtraSerializer(required=False)
    provisional = ProvContCreateSerializer(required=False, read_only=True)
    vendor = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_vendor=True),
                                                default=VendorDefault(),
                                                allow_null=False)
    term_detail = serializers.PrimaryKeyRelatedField(queryset=TermDetail.objects.filter(is_default=True),
                                                     default=TermDetailDefault(),
                                                     allow_null=False,
                                                     help_text="약관 상세 내역")
    status = serializers.PrimaryKeyRelatedField(queryset=ContractStatus.objects.all(),
                                                default=ContractStatusDefault(),
                                                required=False, allow_null=False)

    class Meta:
        model = Contract
        fields = '__all__'

        extra_kwargs = {
            'account_number': {'required': False, 'allow_null': True, 'write_only': True},
            'account_alias': {'required': False, 'allow_null': True, 'write_only': True},
            'rebalancing': {'read_only': True},
            'cancel_reason': {'read_only': True},
            'status': {'read_only': True},
        }

    def validate(self, attrs):
        user = attrs['user']
        contract_type = attrs['contract_type']

        if Contract.objects.filter(user=user, contract_type=contract_type, is_canceled=False).exists():
            raise ValidationError("this user already has {0} contract.".format(contract_type))

        return attrs

    def create(self, validated_data):
        condition = validated_data.get('condition')
        if condition:
            del validated_data['condition']

        extra = validated_data.get('extra')
        if extra:
            del validated_data['extra']

        instance = super().create(validated_data)

        if condition:
            Condition.objects.create(**dict({'contract': instance, **condition}))

        if extra:
            Extra.objects.create(**dict({'contract': instance, **extra}))

        return instance


class ContractSimpleSerializer(ContractSerializer):
    contract_id = serializers.UUIDField(source='id')

    class Meta:
        model = Contract
        fields = ('contract_id', 'contract_type', 'risk_type',
                  'account_alias', 'reb_required', 'reb_status', 'status')
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }


class UserContractSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='profile.name', read_only=True, help_text='유저명')
    ci = serializers.CharField(source='profile.ci', read_only=True)
    ci_hash = serializers.CharField(source='profile.ci_hash', read_only=True)
    ci_encrypted = serializers.CharField(source='profile.get_encrypted_ci', read_only=True)
    contracts = ContractSimpleSerializer(source='contract_set.get_active_contracts', many=True)

    class Meta:
        model = get_user_model()

        fields = ('id', 'name', 'ci', 'ci_hash', 'ci_encrypted', 'contracts',)

        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }

    def get_contracts(self, instance):
        return ContractSimpleSerializer(
            [item for item in instance.contract_set.all() if item.is_canceled is False], many=True).data


class UserAvailableCancelContractSerializer(UserContractSerializer):
    contracts = ContractSimpleSerializer(source='contract_set.get_available_cancel_contracts', many=True)


class AssetChartSerializer(serializers.ModelSerializer):
    series = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = ('id', 'series')

    def get_series(self, obj):
        df = obj.assets_history_df
        try:
            df['evaluation_amount'] = df['deposit'] + df['balance']
            return json.loads((df['evaluation_amount'] / df['base'] * 100 - 100).to_json())
        except:
            return {}


class AssetAmountChartSerializer(serializers.ModelSerializer):
    evaluation_amount = serializers.SerializerMethodField()
    base = serializers.SerializerMethodField()
    deposit = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = ('id', 'base', 'evaluation_amount', 'deposit')

    def get_evaluation_amount(self, obj):
        try:
            df = obj.assets_history_df
            return json.loads((df['deposit'] + df['balance']).to_json())
        except:
            return {}

    def get_base(self, obj):
        try:
            df = obj.assets_history_df
            return json.loads(df['base'].to_json())
        except:
            return {}

    def get_deposit(self, obj):
        df = obj.assets_history_df
        # prev_deposit은 전일자 예수금이므로 index에서 하루를 뺴준다.
        try:
            df = df.set_index(df['prev_deposit'].index.values - pd.Timedelta(days=1))
            return json.loads((df['prev_deposit'].where(df['prev_deposit'] != 0).dropna()).to_json())
        except:
            return {}


class OrderProxyRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(help_text='비밀번호(암호화 적용)', write_only=True, required=True)
    condition = ConditionSerializer(help_text='계약 조건', read_only=True)
    response = serializers.DictField(help_text='증권사 응답값', read_only=True, source='realtime')

    class Meta:
        model = Contract
        fields = ('status', 'condition', 'password', 'response')
        extra_kwargs = {
            'status': {'read_only': True, }
        }

        error_status_codes = {
            status.HTTP_400_BAD_REQUEST: None,
            status.HTTP_404_NOT_FOUND: None,
            status.HTTP_412_PRECONDITION_FAILED: '증권사 연계 API 동작 오류',
            status.HTTP_428_PRECONDITION_REQUIRED: '요구 데이터 누락',
        }

    def is_valid(self, raise_exception=False):
        if super().is_valid(raise_exception=raise_exception):
            contract_type = self.instance.contract_type

            try:
                condition = self.instance.condition
            except Exception as e:
                raise PreconditionRequired(e)

            if contract_type.operation_type != ContractTypeChoices.OPERATION_TYPE.D:
                raise exceptions.ValidationError({
                    'contract_type': 'invalid contract_type for this action.'
                })

            if not condition or not condition.sign:
                raise PreconditionRequired({
                    'condition': 'sign data required'
                })
            return True
        return False

    def get_realtime_data(self, instance, field_name):
        return instance.realtime.get(field_name, None) if instance.realtime else None

    def account_order_proxy(self, instance):
        vendor_code = instance.vendor.vendor_props.code
        account_extra = {}
        extra = getattr(instance, 'extra', None)
        if extra:
            account_extra = {'strategy_code': extra.strategy_code}

        if vendor_code == 'hanaw':
            account_extra = {'account_alias': instance.account_alias}

        _risk_type = instance.risk_type
        if _risk_type is None:
            _risk_type = instance.user.profile.risk_type

        # 원장서버에 운영계좌 등록처리
        resp = account_adapter.request('api/v1/accounts/', data={
            'vendor_code': vendor_code,
            'account_number': instance.account_number,
            'account_type': instance.contract_type.asset_type,
            'risk_type': _risk_type,
            **account_extra
        })

        return resp

    def upload_document(self, instance, context, key_names):
        vendor_code = instance.vendor.vendor_props.code

        endpoint = '/api/v1/{}/document'.format(vendor_code)
        contract_type = 'OEA'
        if vendor_code == 'hanaw':
            contract_type = 'MOEA'
        renderer = ContractPDFRendererFactory.create(contract_type=contract_type, context=context)
        data = renderer.get_b64encode().decode('UTF-8')

        instance.get_realtime_data('realtime', endpoint, **{
            key_names[0]: f"{instance.contract_number}.pdf",
            key_names[1]: data
        })

    def hanaw_order_proxy(self, instance, validated_data=None):
        key_names = ['name', 'file']
        context = {
            'name': instance.user.profile.name,
            'birth_date': instance.user.profile.birth_date,
            'start_date': instance.created_at,
            'email': instance.user.email,
            'securities_company': instance.vendor.vendor_props.company_name,
            'account_number': instance.account_number,
            'signature': instance.condition.sign
        }

        self.upload_document(instance, context, key_names)

        if not self.get_realtime_data(instance, 'dataBody'):
            raise PreconditionFailed(instance.realtime)

    def kb_order_proxy(self, instance, validated_data):
        vendor_code = instance.vendor.vendor_props.code

        # 정보제공동의 신청
        endpoint = '/api/v1/{}/customer/third-party'.format(vendor_code)
        instance.get_realtime_data('realtime', endpoint)

        # 전자문서 업로드 - 이미 업로드 되있으면 추가 업로드 하지 않음.
        key_names = ['file_name', 'data']
        context = {
            'name': instance.user.profile.name,
            'birth_date': instance.user.profile.birth_date,
            'start_date': instance.created_at,
            'email': instance.user.email,
            'securities_company': instance.vendor.vendor_props.company_name,
            'account_number': instance.account_number,
            'signature': instance.condition.sign
        }

        # 전자문서 업로드 - 이미 업로드 되있으면 추가 업로드 하지 않음.
        if not instance.condition.volume_path and not instance.condition.doc_path:
            self.upload_document(instance, context, key_names)

            doc_path = self.get_realtime_data(instance, 'save_path')
            volume_path = self.get_realtime_data(instance, 'volume_name')

            if not doc_path or not volume_path:
                instance.status = get_contract_status(type='vendor_upload_doc_fail')
                instance.save()
                raise PreconditionFailed(detail={
                    'status': get_contract_status(type='vendor_upload_doc_fail').name,
                    'message': 'document upload failed.',
                    'response': self.get_realtime_data(instance, 'dataHeader')
                })
            instance.condition.volume_path = volume_path
            instance.condition.doc_path = doc_path
            instance.condition.save()

        else:
            doc_path = instance.condition.doc_path
            volume_path = instance.condition.volume_path

        # 주문대리인 등록
        endpoint = '/api/v1/{}/account/order-proxy'.format(vendor_code)
        instance.get_realtime_data('realtime', endpoint, **{
            "volume_name": volume_path,
            "acct_pwd": validated_data.get('password'),
            "save_path": doc_path
        })

        set_acct_nickname.apply_async(args=[instance.pk, vendor_code])

        if self.get_realtime_data(instance, 'dataHeader'):
            data_header = self.get_realtime_data(instance, 'dataHeader')
            if data_header.get('processFlag', None) == 'B' or data_header.get('resultCode', None) == '9999':
                instance.status = get_contract_status(type='vendor_order_proxy_fail')
                instance.save()
                raise PreconditionFailed(detail={
                    'status': get_contract_status(type='vendor_order_proxy_fail').name,
                    'message': 'register order proxy failed.',
                    'response': data_header
                })

    def update(self, instance: Contract, validated_data):
        vendor_code = instance.vendor.vendor_props.code

        if settings.USE_REALTIME:
            getattr(self, '{}_order_proxy'.format(vendor_code))(instance, validated_data)
        else:
            # Note: 대외계 실시간 조회 미연결시 로직 추가 구현 필요.
            pass

        resp = self.account_order_proxy(instance)

        if resp:
            if vendor_code != 'hanaw':
                resp = resp.json()
                instance.account_alias = resp.get('accountAlias')
        else:
            raise PreconditionFailed(detail=resp.json())

        status_type = 'vendor_contract_transaction_limit_wait' if vendor_code == 'hanaw' else 'normal'
        instance.status = get_contract_status(type=status_type)
        instance.save()

        return instance


class OrderProxyDeleteSerializer(TerminateContractMixin, serializers.ModelSerializer):
    password = serializers.CharField(help_text='비밀번호(암호화 적용)', write_only=True, required=True)
    response = serializers.DictField(help_text='증권사 응답값', read_only=True, source='realtime')

    class Meta:
        model = Contract
        fields = ('status', 'password', 'response')
        extra_kwargs = {
            'status': {'read_only': True, }
        }

        error_status_codes = {
            status.HTTP_400_BAD_REQUEST: None,
            status.HTTP_404_NOT_FOUND: None,
            status.HTTP_412_PRECONDITION_FAILED: '증권사 연계 API 동작 오류',
            status.HTTP_428_PRECONDITION_REQUIRED: '요구 데이터 누락',
        }

    def is_valid(self, raise_exception=False):
        if super().is_valid(raise_exception=raise_exception):
            contract_type = self.instance.contract_type

            if contract_type.operation_type != ContractTypeChoices.OPERATION_TYPE.D:
                raise exceptions.ValidationError({
                    'contract_type': 'invalid contract_type for this action.'
                })

            if self.instance.status.code not in [get_contract_status(type='vendor_order_proxy_cancel', code=True),
                                                 get_contract_status(type='vendor_order_proxy_cancel_fail', code=True)]:
                raise exceptions.ValidationError({
                    'status': f'invalid contract status - '
                              f'need {get_contract_status(type="vendor_order_proxy_cancel").name} or '
                              f'{get_contract_status(type="vendor_order_proxy_cancel_fail").name}'
                })
            return True
        return False

    def get_realtime_data(self, instance, field_name):
        return instance.realtime.get(field_name, None) if instance.realtime else None

    def update(self, instance, validated_data):
        if settings.USE_REALTIME:
            self.terminate_vendor_proxy(instance=instance)
        else:
            # Note: 대외계 실시간 조회 미연결시 로직 추가 구현 필요.
            pass

        # 원장서버에 운영계좌 해지 처리
        resp = account_adapter.request(f'api/v1/accounts/{instance.account_alias}', method='DELETE')

        # 계좌 해지 완료 처리
        instance.is_canceled = True
        instance.status = get_contract_status(type='canceled')
        instance.save()

        return instance


class KBAccountOpenStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ('contract_id', 'contract_status', 'context', 'status')
        extra_kwargs = {
            'contract_id': {'read_only': True},
            'contract_status': {'read_only': True},
            'context': {'read_only': True},
            'status': {'write_only': True},
        }

    contract_id = serializers.UUIDField(read_only=True, source='id')
    contract_status = serializers.UUIDField(read_only=True, source='status')
    context = serializers.SerializerMethodField(default={})
    status = serializers.ChoiceField(write_only=True,
                                     choices=ProvisionalContractChoices.ACCOUNT_OPEN_STEP_STATUS)

    def check_account_open_rule(self):
        if self.instance.contract_type.operation_type == ContractTypeChoices.OPERATION_TYPE.A:
            return True

        latest_account_open_contracts = Contract.objects \
            .get_latest_account_open_contract() \
            .filter(user=self.instance.user, vendor=self.instance.vendor,
                    contract_type__operation_type=ContractTypeChoices.OPERATION_TYPE.D)

        if latest_account_open_contracts.exists():
            last_contract = latest_account_open_contracts.latest('acct_completed_at')
            raise PreconditionFailed(detail={
                'last_acct_completed_at': last_contract.acct_completed_at,
                'acct_open_available_at': last_contract.acct_completed_at + BDay(ACCOUNT_MULTIPLE_DUE_DAY),
            })
        return True

    def update(self, instance, validated_data):
        self.instance: Contract
        self.instance.provisional.update_step(
            step_id=ProvisionalContract.ACCOUNT_OPEN_STEP_ID,
            **{'status': validated_data['status']})
        self.instance.provisional.save(update_fields=['step'])
        return self.instance

    def to_representation(self, instance):
        return {'contract_id': instance.id,
                'contract_status': instance.status.code,
                'context': instance.provisional.load_step(ProvisionalContract.ACCOUNT_OPEN_STEP_ID)}


class KBUserInforRespSerializer(serializers.Serializer):
    class KBUserInforRespDataSerializer(serializers.Serializer):
        secPINNumber = serializers.CharField(help_text="현대 Pin", required=False)

    dataBody = KBUserInforRespDataSerializer(required=False)


class KBThirdPartyAgreementRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ('id', 'status',)
        extra_kwargs = {
            'status': {'read_only': True, }
        }

    def update_context(self, hpin):
        self.instance: Contract
        self.instance.user.profile.config = {'hpin': hpin}
        self.instance.user.profile.save(update_fields=['config'])

    def get_realtime_data(self, instance, field_name):
        return instance.realtime.get(field_name, None) if instance.realtime else None

    def to_representation(self, instance):
        vendor_code = instance.vendor.vendor_props.code
        endpoint = f"/api/v1/{vendor_code}/customer/third-party"
        response = instance.get_realtime_data('realtime', endpoint=endpoint)

        # KB 자문의 경우 BaaS 제3자 동의
        if instance.contract_type.operation_type == ContractTypeChoices.OPERATION_TYPE.A:
            endpoint = f"/api/v1/{vendor_code}/baas/third-party"
            response = instance.get_realtime_data('realtime', endpoint=endpoint)

            if not response:
                raise PreconditionFailed(instance.realtime)

        # Oauth Token 발급
        endpoint = '/api/v1/{}/oauth'.format(vendor_code)
        instance.get_realtime_data('realtime', endpoint)
        access_token = self.get_realtime_data(instance, 'access_token')

        endpoint = f"/api/v1/{vendor_code}/customer/info"
        response = instance.get_realtime_data('realtime', endpoint=endpoint,
                                              **{
                                                  "access_token": access_token
                                              })
        if not response:
            raise PreconditionFailed(instance.realtime)

        output_serializer = KBUserInforRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class OCRIdentificationResponseSerializer(serializers.Serializer):
    ID_TYPE_MAP = {
        "주민등록증": "01",
        "운전면허증": "02"
    }

    masked_image = serializers.CharField(source="image_encode")
    extract_score = serializers.IntegerField()
    id_type = serializers.SerializerMethodField(help_text="신분증 타입 ID")
    customer_no = serializers.SerializerMethodField(help_text="주민번호 암호화값")
    customer_name = serializers.SerializerMethodField(help_text="고객명")
    customer_issue_date = serializers.SerializerMethodField(help_text="발급일자")
    form_name = serializers.CharField(help_text="신분증 종류")
    license_no = serializers.SerializerMethodField(help_text="면허번호")
    veterans_no = serializers.CharField(default="", allow_blank=True)
    fingerprint_info = serializers.CharField(allow_blank=True, default="")
    photo_info = serializers.CharField(allow_blank=True, source="extract_feature_encode")
    customer_no_change_flag = serializers.CharField(default='N')
    customer_name_change_flag = serializers.CharField(default='N')
    customer_issue_change_flag = serializers.CharField(default='N')
    front_image = serializers.CharField(source="image_encode_enc")

    def get_id_type(self, data_body):
        return self.ID_TYPE_MAP.get(data_body['form_name'], "")

    def get_customer_no(self, data_body):
        try:
            return data_body['fields']['주민번호']['enc_value']
        except KeyError:
            return ""

    def get_license_no(self, data_body):
        try:
            return data_body['fields']['면허번호']['enc_value']
        except KeyError:
            return ""

    def get_customer_name(self, data_body):
        try:
            return data_body['fields']['이름']['value']
        except KeyError:
            return ""

    def get_customer_issue_date(self, data_body):
        try:
            return data_body['fields']['날짜']['value']
        except KeyError:
            return ""

    def to_internal_value(self, data):
        data_body = data['dataBody']
        data_body['fields'] = {}

        for row in data_body['field_results']:
            data_body['fields'][row['display_name']] = row
        return data_body


class OCRIdentificationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ('status', 'id_card_type', 'encoded_image')
        extra_kwargs = {
            'status': {'read_only': True, }
        }

    # TODO 신분증 결과는 임의로 설정 후, 결과 값 기준으로 ID 부여
    id_card_type = serializers.HiddenField(help_text="신분증 타입", default="1")
    encoded_image = serializers.CharField(help_text="Base64 인코딩 이미지")

    def parse_image(self, instance: Contract):
        vendor_code = instance.vendor.vendor_props.code
        endpoint = f"/api/v1/{vendor_code}/account/identification/ocr"

        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(self.instance.realtime)
        return response


class IdentificationSaveCopyRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = (
            "id",
            "handle_classification",
            "accept_date",
            "req_seq",
            "customer_name",
            "customer_pin_number",
            "identify_tel",
            "id_card_code",
            "id_card_recognition",
            "identify_code",
            "identify_result_code"
        )

    handle_classification = serializers.CharField(help_text="처리구분", default="1")
    accept_date = serializers.CharField(help_text="검증일자")
    req_seq = serializers.CharField(help_text="신분증일련번호")
    customer_name = serializers.CharField(help_text="고객명")
    customer_pin_number = serializers.CharField(help_text="고객 H-Pin")
    id_card_code = serializers.CharField(help_text="신분증 구분코드")
    identify_tel = serializers.CharField(help_text="본인인증 전화번호")
    id_card_recognition = serializers.CharField(default="0")
    identify_code = serializers.CharField(default="1", help_text="전화인증 코드")
    identify_result_code = serializers.CharField(default="1")

    def get_identify_tel(self, instance: Contract):
        return instance.user.profile.phone

    def get_customer_pin_number(self, instance: Contract):
        return instance.user.profile.hpin

    def to_internal_value(self, data):
        data["id_card_code"] = str(int(data['id_type']))
        data["identify_tel"] = self.get_identify_tel(self.instance)
        data["customer_pin_number"] = self.get_customer_pin_number(self.instance)
        data["req_seq"] = data['req_seq']
        data["accept_date"] = timezone.now().strftime("%Y%m%d")
        return super().to_internal_value(data)


class OCRIdentificationValidateRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ('id',
                  'id_type', 'customer_no', 'customer_name', 'customer_issue_date',
                  'license_no', 'veterans_no', 'fingerprint_info', 'photo_info', 'extract_score',
                  'customer_no_change_flag', 'customer_name_change_flag', 'customer_issue_change_flag',
                  'front_image'
                  )

    id_type = serializers.CharField(help_text="신분증 구분")
    customer_no = serializers.CharField(help_text="고객번호", source="identification_no")
    customer_name = serializers.CharField(help_text="고객명")
    customer_issue_date = serializers.CharField(help_text="발급일자")
    license_no = serializers.CharField(default="", allow_blank=True)
    veterans_no = serializers.CharField(default="", allow_blank=True)
    fingerprint_info = serializers.CharField(default="", allow_blank=True)
    photo_info = serializers.CharField(allow_blank=True)
    extract_score = serializers.IntegerField()
    customer_no_change_flag = serializers.CharField()
    customer_name_change_flag = serializers.CharField()
    customer_issue_change_flag = serializers.CharField()
    front_image = serializers.CharField()

    def get_fingerprint_info_size(self, instance):
        return str(len(instance['fngrInfo']))

    def get_photo_info_size(self, instance):
        return str(len(instance['photoInfo']))

    def get_front_image_size(self, instance):
        return str(len(instance['frontImage']))

    def update(self, instance: Contract, validated_data):
        # 신분증 검증
        vendor_code = instance.vendor.vendor_props.code
        endpoint = f"/api/v1/{vendor_code}/account/identification/validate"
        validate_resp = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not validate_resp:
            raise PreconditionFailed(instance.realtime)

        # 신분증 사본 등록
        req_seq = validate_resp['dataBody']['req_seq']
        copy_id_endpoint = f"/api/v1/{vendor_code}/account/identification"
        copy_id_card_serializer = IdentificationSaveCopyRequestSerializer(
            instance=instance,
            data={'req_seq': req_seq,
                  **self.validated_data})
        copy_id_card_serializer.is_valid(raise_exception=True)
        copy_save_resp = instance.get_realtime_data('realtime', copy_id_endpoint,
                                                    **copy_id_card_serializer.validated_data)

        # 스텝 저장
        if copy_save_resp:
            current_step = {
                "req_seq": req_seq,
                "id_type": copy_id_card_serializer.validated_data['id_card_code'],
                "validated_at": copy_id_card_serializer.validated_data['accept_date']
            }

            self.instance.provisional.update_step(
                ProvisionalContract.ACCOUNT_OPEN_STEP_ID,
                **current_step)
            self.instance.provisional.save(update_fields=['step'])
            return current_step
        else:
            raise PreconditionFailed(instance.realtime)


class KBAccountOpenAddressSearchRespSerializer(serializers.Serializer):
    class AddressSearchResponseDataSerializer(serializers.Serializer):
        class AddressSearchResponseRecordRowSerializer(serializers.Serializer):
            new_post_no = serializers.CharField(help_text="새우편번호")
            address_post_seq = serializers.CharField(help_text="지번우편일련번호")
            address = serializers.CharField(help_text="시도/시군구/읍면동")
            address_bnj = serializers.CharField(help_text="번지")
            new_address = serializers.CharField(help_text="시도/시군구/읍면/도로명")
            underground_flag = serializers.CharField(help_text="지하여부(0: 지하X, 1: 지하O)",
                                                     allow_blank=True)
            building_head_no = serializers.CharField(help_text="건물본번호")
            building_sub_no = serializers.CharField(help_text="건물부번호")
            building_name = serializers.CharField(default="",
                                                  allow_blank=True, help_text="건물명")
            building_manage_code = serializers.CharField(help_text="건물관리코드")
            legal_dong_code = serializers.CharField(help_text="법정동코드")
            road_name_code = serializers.CharField(help_text="도로명코드")
            eup_myeon_seq = serializers.CharField(help_text="읍면일련번호")
            road_name_mapping_seq = serializers.CharField(help_text="도로명매핑일련번호")
            address_mapping_seq = serializers.CharField(help_text="지번매핑일련번호")
            combined_building_management_code = serializers.CharField(help_text="조합된건물관리코드")
            si_do = serializers.CharField(help_text="시도")
            si_gun_gu = serializers.CharField(help_text="시군구")
            eup_myeon_dong = serializers.CharField(help_text="읍면동")
            road_name = serializers.CharField(help_text="도로명")
            post_seq = serializers.CharField(help_text="우편일련번호")

            def to_representation(self, instance):
                return super().to_representation(instance)

        total_cnt = serializers.IntegerField(source='tlCnt', help_text="총건수")
        page_index = serializers.IntegerField(source='rqsPg', help_text="요청페이지")
        record_continuance_flag = serializers.BooleanField(source='rcrdCnF', help_text="레코드연속여부")
        response_cnt = serializers.IntegerField(source='rspnsCnt', help_text="응답건수")
        response_code = serializers.CharField(source='rspnsCd', help_text="응답코드")
        keyword = serializers.CharField(source='inptData', help_text="입력데이터")
        Record1 = AddressSearchResponseRecordRowSerializer(many=True)

        def to_representation(self, instance):
            representation = super().to_representation(instance)
            representation['candidates'] = representation.pop('Record1', [])
            return representation

    dataBody = AddressSearchResponseDataSerializer(required=False)


class KBAddressSerialNumberSearchRespSerializers(serializers.Serializer):
    class KBAddressSerialNumberSearchRespDataSerializers(serializers.Serializer):
        output_len = serializers.CharField(help_text="출력길이", required=False)
        output_classification = serializers.CharField(help_text="출력구분", required=False)
        output_msg = serializers.CharField(help_text="출력메시지", allow_blank=True, required=False)
        post_seq = serializers.CharField(help_text="우편일련번호", required=False)

    dataBody = KBAddressSerialNumberSearchRespDataSerializers(required=False)

    def to_representation(self, instance):
        return super().to_representation(instance=instance)


class KBAccountOpenAddressSearchSerialReqSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ('id', 'road_name_code', 'underground_flag', 'building_head_no', 'building_sub_no')

    road_name_code = serializers.CharField(help_text="도로명코드")
    underground_flag = serializers.ChoiceField(choices=[('0', '지하X'), ('1', '지하O')],
                                               help_text="지하여부")
    building_head_no = serializers.CharField(help_text="건물본번호")
    building_sub_no = serializers.CharField(help_text="건물부번호")

    def to_representation(self, instance):
        endpoint = "/api/v1/kb/account/customer/address-serial"
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        output_serializer = KBAddressSerialNumberSearchRespSerializers(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class KBAccountOpenAddressSearchReqSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ('id', 'status', "page_index", "keyword")
        extra_kwargs = {
            'status': {'read_only': True, }
        }

    page_index = serializers.IntegerField(default=1, help_text="페이지 인덱스")
    keyword = serializers.CharField(help_text="페이지 인덱스")

    def to_representation(self, instance):
        endpoint = "/api/v1/kb/account/customer/address"
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        output_serializer = KBAccountOpenAddressSearchRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class AddressSerialNumberSearchResponseSerializers(serializers.Serializer):
    class AddressSerialNumberSearchResponseDataSerializers(serializers.Serializer):
        output_msg = serializers.CharField(help_text="출력메시지", allow_blank=True)
        post_seq = serializers.CharField(help_text="우편일련번호")

    dataBody = AddressSerialNumberSearchResponseDataSerializers(required=False)


class RegisterCustomerInformationResponseSerializer(serializers.Serializer):
    # 고객정보입력
    class RegisterCustomerInformationResponseDataSerializer(serializers.Serializer):
        output_msg = serializers.CharField(source='oMsg', help_text="출력메시지", allow_blank=True)
        customer_no = serializers.CharField(source='csNo', help_text="고객번호")

    dataBody = RegisterCustomerInformationResponseDataSerializer(required=False)


class RegisterCustomerInformationRequestSerializer(serializers.Serializer):
    post_no = serializers.CharField(help_text="우편번호")
    post_seq = serializers.CharField(help_text="우편일련번호")
    dong_floor_address = serializers.CharField(help_text="동 이하 주소")
    occupation_code = serializers.ChoiceField(choices=[('0000', '선택'), ('0001', '공무원'), ('0002', '회사원'),
                                                       ('0003', '자영업'), ('0004', '농림 수산'), ('0005', '주부'),
                                                       ('0006', '언론인'), ('0007', '교직원'), ('0008', '정치인'),
                                                       ('0009', '연예인'), ('0010', '군인'), ('0011', '운동선수'),
                                                       ('0012', '법조인'), ('0013', '예술가'), ('0014', '종교인'),
                                                       ('0015', '대학생'), ('0016', '초중고'), ('9998', '전문직'),
                                                       ('9999', '기타')],
                                              help_text="직업코드")
    occupation_detail_code = serializers.ChoiceField(choices=[('0299', '기타 회사원'), ('0201', '카지노/경마/복권등 도박종사자'),
                                                              ('0202', '사 금융(대부/환전/전당포)종사자'),
                                                              ('0203', '귀금속 제품 도/소매 종사자'),
                                                              ('0204', '부동산 매매 종사자'), ('0205', '상품 경매(예술품 중개)'),
                                                              ('0206', '무기 등 군수 제조 및 제공 종사자'),
                                                              ('0207', '조세회피지역에 설립된 기업 등 종사자'),
                                                              ('0399', '기타 자영업자'), ('0301', '카지노/경마/복권등 도박'),
                                                              ('0302', '사 금융(대부/환전/전당포)'), ('0303', '귀금속 제품 도/소매'),
                                                              ('0304', '유흥주점'), ('0305', '부동산 매매'),
                                                              ('0306', '상품 경매(예술품 중개)'), ('0307', '주유소 및 편의점'),
                                                              ('0308', '무기 등 군수 제조 및 제공'), ('0309', '자동차 딜러'),
                                                              ('0310', '요트/보트 딜러'), ('0311', '여행사'),
                                                              ('0312', '기타현금집중업(레스토랑/주차장/극장 등)'),
                                                              ('0313', '수출입 무역'), ('0314', '조세회피지역에 설립된 기업 등'),
                                                              ('1201', '변호사'), ('1202', '법무사'), ('1203', '변리사'),
                                                              ('1299', '기타 법률관련'), ('9801', '회계사'),
                                                              ('9802', '세무사'), ('9803', '자산운용가'),
                                                              ('9804', '증권 및 외환딜러'), ('9805', '보험설계사'),
                                                              ('9806', '간접투자증권판매인'), ('9807', '경영컨설턴트'),
                                                              ('9808', '기업 인수/합병 전문가'),
                                                              ('9809', '기타 금융 및 보험 관련 전문가'), ('9810', '의사'),
                                                              ('9811', '한의사'), ('9812', '수의사'), ('9813', '약사'),
                                                              ('9899', '기타전문가')],
                                                     help_text="직업세부코드",
                                                     allow_null=True,
                                                     allow_blank=True,
                                                     required=False)
    mobile = serializers.CharField(help_text="휴대전화번호 (010 12345678)")
    email = serializers.CharField(help_text="이메일 주소", required=False)
    birth_date = serializers.CharField(help_text="생년월일")
    identification_card_seq = serializers.CharField(help_text="신분증일련번호", required=True, source="req_seq")
    financial_deal_object = serializers.ChoiceField(choices=[('1', '급여 및 생활비'), ('2', '사업상거래'), ('3', '저축및투자'),
                                                             ('4', '결제-보험료납부비'), ('5', '결제-공과금납부'),
                                                             ('6', '결제-카드대금'), ('7', '결제-대출원리금상환비'),
                                                             ('8', '기타'), ('9', '상속-증여성거래'), ('A', '부채상환'),
                                                             ('B', '노후생활 자금마련'), ('C', '부동산 구입 자금마련'),
                                                             ('D', '자녀교육 및 결혼 자금마련'), ('E', '적극적 재산증식'),
                                                             ('F', '공모주청약 실적유지'), ('G', '결제-보험료,공과금,카드,대출금 등'),
                                                             ('H', '대리인 거래(개인)')],
                                                    help_text="금융거래목적(자금목적)")
    funds_kind = serializers.ChoiceField(choices=[('01', '급여'), ('02', '자산처분'), ('03', '상속,증여'), ('04', '사업소득'),
                                                  ('05', '여유자금'), ('06', '대출금'), ('09', '기타'),
                                                  ('11', '금융소득(이자,배당)'), ('12', '부동산 임대소득'), ('13', '사업소득'),
                                                  ('14', '근로소득'), ('15', '퇴직소득'), ('16', '부동산/주식 등 양도소득'),
                                                  ('17', '상속,증여'), ('18', '여유자금'), ('19', '금융기관 등 차입'),
                                                  ('21', '대리인 거래(개인)')],
                                         help_text="자금종류(자금출처)")
    customer_sex = serializers.ChoiceField(choices=[('1', '남자'), ('2', '여자'), ('9', '기타')],
                                           help_text="성별")
    real_name_confirm_no = serializers.CharField(help_text="H-Pin", required=False, source="customer_pin_number")
    product_no = serializers.ChoiceField(choices=[('01', '증권거래'), ('03', '입출금거래CMA'), ('07', '선물옵션거래'),
                                                  ('08', 'IRP'), ('10', '연금저축')],
                                         initial="01",
                                         help_text="상품그룹코드",
                                         default="01",
                                         required=False,
                                         allow_null=True,
                                         allow_blank=True)

    def validate(self, attrs):
        attrs['customer_pin_number'] = self.instance.user.profile.hpin
        attrs['email'] = self.instance.user.email
        return attrs

    def update_context(self, cs_no):
        self.instance: Contract
        self.instance.provisional.update_step(
            step_id=ProvisionalContract.ACCOUNT_OPEN_STEP_ID,
            **{'cs_no': cs_no})
        self.instance.provisional.save(update_fields=['step'])

    def update(self, instance, validated_data):
        self.instance: Contract
        self.instance.provisional.update_step(
            step_id=ProvisionalContract.ACCOUNT_OPEN_STEP_ID,
            **{'post_no': validated_data['post_no'],
               'post_seq': validated_data['post_seq'],
               'dong_floor_address': validated_data['dong_floor_address']})
        self.instance.provisional.save(update_fields=['step'])

        endpoint = "/api/v1/kb/account/customer/register"
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        output_serializer = RegisterCustomerInformationResponseSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        self.update_context(output_serializer.data['dataBody']['customer_no'])
        return self.instance


class AccountOpenPasswordValidationRespSerializer(serializers.Serializer):
    class AccountOpenPasswordValidationRespDataSerializer(serializers.Serializer):
        output_msg = serializers.CharField(source='oMsg', help_text="출력메시지", allow_blank=True)

    dataBody = AccountOpenPasswordValidationRespDataSerializer(required=False)


class AccountOpenPasswordValidationReqSerializer(serializers.Serializer):
    handle_classification = serializers.HiddenField(help_text="처리구분", default="5")
    identification_card_seq = serializers.CharField(help_text="신분증일련번호", required=True, source="req_seq")
    password = serializers.CharField(help_text="비밀번호 ETOE (처리구분 5-비밀번호 검증시)", allow_blank=True)
    real_name_confirm_no = serializers.CharField(help_text="H-Pin", required=False, source="customer_pin_number")

    def validate(self, attrs):
        attrs['customer_pin_number'] = self.instance.user.profile.hpin
        return attrs

    def to_representation(self, instance):
        endpoint = "/api/v1/kb/account/password/validate"
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        output_serializer = AccountOpenPasswordValidationRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class AccountOpenRespSerializer(serializers.Serializer):
    class AccountOpenRespDataSerializer(serializers.Serializer):
        output_msg = serializers.CharField(help_text="출력메시지", allow_blank=True)
        entrust_acct_no = serializers.CharField(help_text="채번된 위탁계좌번호", allow_blank=True)
        cma_acct_no = serializers.CharField(help_text="채번된 CMA 계좌번호", allow_blank=True)
        futures_options_acct_no = serializers.CharField(help_text="채번된 펀드 계좌번호", allow_blank=True)
        foreign_stock_exclusive_acct_no = serializers.CharField(help_text="채번된 해외주식 전용 계좌번호", allow_blank=True)
        isa_acct_no = serializers.CharField(help_text="채번된 ISA 계좌번호", allow_blank=True)
        irp_acct_no = serializers.CharField(help_text="채번된 IRP 계좌번호", allow_blank=True)
        pension_acct_no = serializers.CharField(help_text="채번된 연금 계좌번호", allow_blank=True)

    dataBody = AccountOpenRespDataSerializer(required=False)


class AccountOpenReqSerializer(serializers.Serializer):
    identification_card_seq = serializers.CharField(help_text="신분증일련번호", required=True, source="req_seq")
    password = serializers.CharField(help_text="비밀번호 ETOE (처리구분 5-비밀번호 검증시)", allow_blank=True)
    password_confirm = serializers.CharField(help_text="비밀번호 ETOE (처리구분 5-비밀번호 검증시)", allow_blank=True)
    real_name_confirm_no = serializers.CharField(help_text="H-Pin", required=False, source="customer_pin_number")
    product_no = serializers.ChoiceField(help_text="계좌 타입(FEP 통신용 필드)",
                                         choices=[('01', '증권거래'), ('03', '입출금거래CMA'), ('07', '선물옵션거래'),
                                                  ('08', 'IRP'), ('10', '연금저축')],
                                         initial="01",
                                         default="01",
                                         required=False,
                                         allow_blank=True,
                                         allow_null=True)
    contract_period = serializers.CharField(help_text="계약기간 - 연금(60 ~ 110 month)", default="", allow_blank=True)

    def validate(self, attrs):
        attrs['customer_pin_number'] = self.instance.user.profile.hpin
        return attrs

    def validate_contract_period(self, contract_period):
        if self.initial_data.get("product_no") == "10":
            contract_period = "60"
        return contract_period

    def to_representation(self, instance):
        endpoint = "/api/v1/kb/account/new"
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        output_serializer = AccountOpenRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']

    def update_context(self, acct_no):
        self.instance: Contract
        self.instance.provisional.update_step(step_id=ProvisionalContract.ACCOUNT_OPEN_STEP_ID,
                                              **{'entrust_account_no': acct_no})
        self.instance.provisional.save(update_fields=['step'])


class AccountValidationRespSerializer(serializers.Serializer):
    class AccountValidationRespDataSerializer(serializers.Serializer):
        output_msg = serializers.CharField(source='oMsg', help_text="출력메시지", allow_blank=True)

    dataBody = AccountValidationRespDataSerializer(required=False)


class AccountValidationReqSerializer(serializers.Serializer):
    non_contact_withdraw_confirm_code = serializers.CharField(help_text="1원 이체 받아 확인할 코드", source="withdraw_code")
    password = serializers.CharField(help_text="비밀번호 ETOE",
                                     allow_null=True,
                                     allow_blank=True,
                                     required=False)

    def validate(self, attrs):
        step = self.instance.provisional.load_step(ProvisionalContract.ACCOUNT_OPEN_STEP_ID)
        attrs['acct_no'] = step.get('entrust_account_no', None) or step.get('acct_no', None)
        endpoint = "/api/v1/kb/account/verification"
        response = self.instance.get_realtime_data('realtime', endpoint, **attrs)
        if not response:
            raise PreconditionFailed(self.instance.realtime)
        output_serializer = AccountValidationRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return attrs


class AccountCertificationRespSerializer(serializers.Serializer):
    class AccountCertificationRespDataSerializer(serializers.Serializer):
        output_msg = serializers.CharField(source='oMsg', help_text="출력메시지", allow_blank=True)

    dataBody = AccountCertificationRespDataSerializer(required=False)


class AccountCertificationReqSerializer(serializers.Serializer):
    non_contact_withdraw_confirm_code = serializers.CharField(help_text="1원 이체 코드", write_only=True,
                                                              source="withdraw_code")
    password = serializers.CharField(help_text="비밀번호 ETOE",
                                     allow_null=True,
                                     allow_blank=True,
                                     required=False)

    def validate(self, attrs):
        step = self.instance.provisional.load_step(ProvisionalContract.ACCOUNT_OPEN_STEP_ID)
        attrs['acct_no'] = step.get('entrust_account_no', None) or step.get('acct_no', None)
        return attrs

    def to_representation(self, instance):
        endpoint = "/api/v1/kb/account/verification"
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        output_serializer = AccountCertificationRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class AccountRegisterValidationRespSerializer(serializers.Serializer):
    class AccountRegisterValidationRespDataSerializer(serializers.Serializer):
        output_msg = serializers.CharField(source='oMsg', help_text="출력메시지", allow_blank=True)

    dataBody = AccountRegisterValidationRespDataSerializer(required=False)


class AccountRegisterValidationReqSerializer(serializers.Serializer):
    identification_card_seq = serializers.CharField(help_text="신분증일련번호", source="req_seq")
    deposit_bank_code = serializers.CharField(source="bank_code", help_text="은행코드번호 3자리")
    deposit_account_no = serializers.CharField(source="bank_acct_no", help_text="1원 이체 받을 입금계좌번호")
    receiver_name = serializers.CharField(source="acct_owner", help_text="1원 이체 받을 입금계좌번호 계좌주인 이름")
    real_name_confirm_no = serializers.CharField(help_text="H-Pin", required=False, source="customer_pin_number")

    def validate(self, attrs):
        step = self.instance.provisional.load_step(ProvisionalContract.ACCOUNT_OPEN_STEP_ID)
        attrs['customer_pin_number'] = self.instance.user.profile.hpin
        attrs['acct_no'] = step.get('entrust_account_no', None) or step.get('acct_no', None)
        return attrs

    def to_representation(self, instance):
        endpoint = "/api/v1/kb/account/verification/register"
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        output_serializer = AccountRegisterValidationRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class GlobalOneMarketRespSerializer(serializers.Serializer):
    class GlobalOneMarketRespDataSerializer(serializers.Serializer):
        output_msg = serializers.CharField(source='oMsg', help_text="출력메시지", allow_blank=True)

    dataBody = GlobalOneMarketRespDataSerializer(required=False)


class GlobalOneMarketReqSerializer(serializers.Serializer):

    def validate(self, attrs):
        step = self.instance.provisional.load_step(ProvisionalContract.ACCOUNT_OPEN_STEP_ID)
        attrs['acct_no'] = step.get('entrust_account_no', None) or step.get('acct_no', None)
        return attrs

    def to_representation(self, instance):
        endpoint = "/api/v1/kb/account/verification/market"
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        output_serializer = AccountRegisterValidationRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class AccountELWDescRespSerializer(serializers.Serializer):
    # ELW거래설명서교부관리
    class AccountELWDescRespDataSerializer(serializers.Serializer):
        output_len = serializers.CharField(help_text="길이", required=False, allow_blank=True)
        output_delimiter = serializers.CharField(help_text="구분", required=False, allow_blank=True)
        output_message = serializers.CharField(help_text="메시지", required=False, allow_blank=True)
        grid_cnt = serializers.CharField(help_text="그리드건수", required=False, allow_blank=True)
        real_name_confirm_no = serializers.CharField(help_text="실명확인번호", required=False,
                                                     source="customer_pin_number", allow_blank=True)
        register_flag = serializers.CharField(help_text="등록여부", required=False, source="is_registered",
                                              allow_blank=True)
        account_no = serializers.CharField(help_text="계좌번호", required=False, source="acct_no", allow_blank=True)
        account_name = serializers.CharField(help_text="계좌명", required=False, source="acct_owner", allow_blank=True)

    dataBody = AccountELWDescRespDataSerializer(required=False)


class AccountELWDescReqSerializer(serializers.Serializer):
    handle_classification = serializers.ChoiceField(default='1', choices=[(1, '등록'), (3, '취소'), (4, '조회')])

    def validate(self, attrs):
        step = self.instance.provisional.load_step(ProvisionalContract.ACCOUNT_OPEN_STEP_ID)
        attrs['acct_no'] = step.get('entrust_account_no', None) or step.get('acct_no', None)
        attrs['customer_pin_number'] = self.instance.user.profile.hpin
        attrs['password'] = ''
        return attrs

    def to_representation(self, instance):
        endpoint = "/api/v1/kb/account/verification/elw"
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        output_serializer = AccountELWDescRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class AuthIdentificationRespSerializer(serializers.Serializer):
    class AuthIdentificationRespDataSerializer(serializers.Serializer):
        output_len = serializers.CharField(help_text="출력길이", required=False)
        output_classification = serializers.CharField(help_text="출력구분", required=False)
        output_msg = serializers.CharField(help_text="출력메시지", required=False)
        hpin_number = serializers.CharField(help_text="현대 pin(고객 HPIN)", required=False)

    dataBody = AuthIdentificationRespDataSerializer(required=False)


class AuthIdentificationReqSerializer(serializers.Serializer):
    identification_no = serializers.CharField(help_text="입력번호(ETOE) - 주민등록번호 암호화된 값")

    def to_representation(self, instance):
        endpoint = 'api/v1/kb/account/customer/hpin'
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)
        output_serializer = AuthIdentificationRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']

    def update_context(self, hpin):
        self.instance: Contract
        self.instance.user.profile.config = {'hpin': hpin}
        self.instance.user.profile.save(update_fields=['config'])


class DecryptETOERespSerializer(serializers.Serializer):
    # 고객 데이타 복호화 (ETOE 복호화)
    class DecryptETOERespDataSerializer(serializers.Serializer):
        dec_data_1 = serializers.CharField(help_text="복호화된 ETOE 데이터", required=False)

    dataBody = DecryptETOERespDataSerializer(required=False)


class DecryptETOEReqSerializer(serializers.Serializer):
    # 고객 데이타 복호화 (ETOE 복호화)
    identification_no = serializers.CharField(source='enc_data_1', help_text="ETOE로 암호화 된 데이터", required=False)

    def validate(self, attrs):
        endpoint = 'api/v1/kb/account/customer/decrypt'
        response = self.instance.get_realtime_data('realtime', endpoint, **attrs)
        if not response:
            raise PreconditionFailed(self.instance.realtime)

        output_serializer = DecryptETOERespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)

        if not self.instance.user.profile.is_validated_user(output_serializer.data['dataBody']['dec_data_1'][:6],
                                                            output_serializer.data['dataBody']['dec_data_1'][6]):
            raise PreconditionFailed("birth_date and gender_code is not match")

        return attrs


class AccountOwnerVerificationRespSerializer(serializers.Serializer):
    # 비대면 실명확인조회 응답
    class AccountOwnerVerificationRespDataSerializer(serializers.Serializer):
        output_len = serializers.CharField(help_text="출력길이", required=False)
        output_classification = serializers.CharField(help_text="출력구분", required=False)
        output_msg = serializers.CharField(help_text="출력메세지", required=False)
        acct_owner = serializers.CharField(help_text="계좌명", required=False)
        acct_no = serializers.CharField(help_text="입금신계좌번호", allow_blank=True, required=False)

    dataBody = AccountOwnerVerificationRespDataSerializer(required=False)


class AccountOwnerVerificationReqSerializer(serializers.Serializer):
    # 비대면 실명확인조회 요청
    deposit_bank_code = serializers.CharField(source='bank_code', help_text="은행코드")
    deposit_account_no = serializers.CharField(source='bank_acct_no', help_text="은행계좌번호")
    receiver_name = serializers.CharField(source='acct_owner', help_text="계좌명")
    real_name_confirm_no = serializers.CharField(help_text="H-Pin", source="customer_pin_number", required=False)

    def validate(self, attrs):
        step = self.instance.provisional.load_step(ProvisionalContract.ACCOUNT_OPEN_STEP_ID)
        attrs['customer_pin_number'] = self.instance.user.profile.hpin
        attrs['acct_no'] = step.get('entrust_account_no', None) or step.get('acct_no', None)

        endpoint = 'api/v1/kb/account/verification/owner'
        response = self.instance.get_realtime_data('realtime', endpoint, **attrs)
        if not response:
            raise PreconditionFailed(self.instance.realtime)

        output_serializer = AccountOwnerVerificationRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)

        return attrs


class KBThirdPartyAdvisoryRespSerializer(serializers.Serializer):
    class ThirdPartyAdvisoryRespDataSerializer(serializers.Serializer):
        output_msg = serializers.CharField(source='oMsg', help_text="출력메시지", allow_blank=True)

    dataBody = ThirdPartyAdvisoryRespDataSerializer(required=False)


class KBThirdPartyAdvisoryReqSerializer(serializers.Serializer):
    # 투자자문계약등록
    password = serializers.CharField(help_text='비밀번호(암호화 적용)', write_only=True, required=True)

    def get_realtime_data(self, instance, field_name):
        return instance.realtime.get(field_name, None) if instance.realtime else None

    def to_representation(self, instance):
        endpoint = "/api/v1/kb/account/advisory"
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)

        if not response:
            instance.change_status(get_contract_status(type='vendor_contract_advisory_fail'))
            raise PreconditionFailed(instance.realtime)
        output_serializer = KBThirdPartyAdvisoryRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)

        _risk_type = instance.risk_type

        if _risk_type is None:
            _risk_type = instance.user.profile.risk_type

        if (instance.contract_number == instance.account_alias):
            # 원장서버에 운영계좌 등록처리
            resp = account_adapter.request('api/v1/accounts/', data={
                'vendor_code': instance.vendor.vendor_props.code,
                'account_number': instance.account_number,
                'account_type': instance.contract_type.asset_type,
                'type': 2,
                'risk_type': _risk_type,
            })

            if resp:
                resp = resp.json()
                instance.account_alias = resp.get('accountAlias')

        vendor_code = instance.vendor.vendor_props.code
        # Oauth Token 발급
        endpoint = '/api/v1/{}/oauth'.format(vendor_code)
        instance.get_realtime_data('realtime', endpoint)
        access_token = self.get_realtime_data(instance, 'access_token')
        set_acct_nickname.apply_async(args=[instance.pk, vendor_code])

        instance.change_status(get_contract_status(type='normal'))
        return output_serializer.data['dataBody']


class AccountFromAllVendorRespSerializer(serializers.Serializer):
    class AccountFromAllVendorRespDataSerializer(serializers.Serializer):
        class AccountFromAllVendorRespRowSerializer(serializers.Serializer):
            acct_no = serializers.CharField(help_text="계좌번호")
            product_type_name = serializers.CharField(help_text="상품유형명", allow_blank=True)
            product_type_code = serializers.CharField(help_text="상품유형코드", allow_blank=True)
            cancel_clsf_name = serializers.CharField(help_text="해지구분명", allow_blank=True)
            new_register_date = serializers.CharField(help_text="신규가입일", allow_blank=True)
            expiry_date = serializers.CharField(help_text="저축만기일")
            register_amt = serializers.CharField(help_text="가입금액")
            register_branch_name = serializers.CharField(help_text="가입지점명")
            saving_type_code = serializers.CharField(help_text="저축종류코드", allow_blank=True)
            inheritance_name = serializers.CharField(help_text="상속여부명", allow_blank=True)
            update_date = serializers.CharField(help_text="최종변경일")
            cancel_date = serializers.CharField(help_text="해지일", allow_blank=True)
            amt = serializers.CharField(help_text="금액")
            bank_code = serializers.CharField(help_text="금융기관코드", allow_blank=True, allow_null=True)
            company_name = serializers.CharField(help_text="기관명")

            def to_representation(self, instance):
                return super().to_representation(instance)

        Record1 = AccountFromAllVendorRespRowSerializer(many=True)

        def to_representation(self, instance):
            representation = super().to_representation(instance)
            representation['candidates'] = representation.pop('Record1', [])
            return representation

    dataBody = AccountFromAllVendorRespDataSerializer(required=False)


class AccountFromAllVendorReqSerializer(serializers.Serializer):
    customer_pin_number = serializers.CharField(help_text="H-Pin", required=False)

    def validate(self, attrs):
        attrs['customer_pin_number'] = self.instance.user.profile.hpin
        return attrs

    def to_representation(self, instance):
        endpoint = 'api/v1/kb/account/all-vendor'
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)

        output_serializer = AccountFromAllVendorRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)

        return output_serializer.data['dataBody']


class AccountPensionLimitRespSerializer(serializers.Serializer):
    # 연금한도변경
    class AccountPensionLimitRespDataSerializer(serializers.Serializer):
        before_amt = serializers.CharField(help_text="", required=False)
        update_amt = serializers.CharField(help_text="", required=False)

    dataBody = AccountPensionLimitRespDataSerializer(required=False)


class AccountPensionLimitReqSerializer(serializers.Serializer):
    update_amt = serializers.CharField(required=True)

    def to_representation(self, instance):
        endpoint = 'api/v1/kb/account/pension/limit'
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)

        output_serializer = AccountPensionLimitRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class AccountPensionDetailRespSerializer(serializers.Serializer):
    # 올해 납입 한도 금액 조회
    class AccountPensionDetailRespDataSerializer(serializers.Serializer):
        limit_amt = serializers.CharField(help_text="설정된 납입한도", required=False)
        payment_amt = serializers.CharField(help_text="이전신청시 기관납입금액 조회", required=False)

    dataBody = AccountPensionDetailRespDataSerializer(required=False)


class AccountPensionDetailReqSerializer(serializers.Serializer):

    def to_representation(self, instance):
        endpoint = 'api/v1/kb/account/pension/detail'
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)
        if not response:
            raise PreconditionFailed(instance.realtime)

        output_serializer = AccountPensionDetailRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class AccountAvailablePensionDetailRespSerializer(serializers.Serializer):
    # 설정 가능한 납입 한도
    class AccountAvailablePensionDetailRespDataSerializer(serializers.Serializer):
        available_limit_amt = serializers.CharField(help_text="", required=False)

    dataBody = AccountAvailablePensionDetailRespDataSerializer(required=False)


class AccountAvailablePensionDetailReqSerializer(serializers.Serializer):

    def validate(self, attrs):
        attrs['customer_pin_number'] = self.instance.user.profile.hpin
        return attrs

    def to_representation(self, instance):
        endpoint = 'api/v1/kb/account/options/detail'
        data = {
            'customer_pin_number': self.validated_data['customer_pin_number'],
            'product_no': "10",
            'handle_classification': "2"
        }
        response = instance.get_realtime_data('realtime', endpoint, **data)
        if not response:
            raise PreconditionFailed(instance.realtime)

        output_serializer = AccountAvailablePensionDetailRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class AccountPensionReceiptRespSerializer(serializers.Serializer):
    class AccountPensionReceiptRespDataSerializer(serializers.Serializer):
        pension_open_date = serializers.CharField(help_text="연금개시예정일자", required=False)
        pension_receipt_date = serializers.CharField(help_text="연금개시가능일자", required=False)

    dataBody = AccountPensionReceiptRespDataSerializer(required=False)


class AccountPensionReceiptReqSerializer(serializers.Serializer):

    def to_representation(self, instance):
        endpoint = 'api/v1/kb/account/pension/receipt'
        response = instance.get_realtime_data('realtime', endpoint, **self.validated_data)

        if not response:
            raise PreconditionFailed(instance.realtime)

        output_serializer = AccountPensionReceiptRespSerializer(data=response)
        output_serializer.is_valid(raise_exception=True)
        return output_serializer.data['dataBody']


class SyncStatusSerializer(serializers.Serializer):

    def check_account(self, instance, response):
        if response and int(response['grid_cnt']):
            for record in response['records']:
                if instance.created_at.strftime('%Y%m%d') <= record['open_date']:
                    instance.status = get_contract_status(type='vendor_account_success')
                    instance.account_number = record['acct_no'] + record['product_no']
                    instance.account_alias = record['acct_alias'] + record['product_no']
                    instance.save()

                    endpoint = '/api/v1/{}/oauth/cache'.format(instance.vendor.vendor_props.code)
                    instance.get_realtime_data('realtime', endpoint)
                    return True
            return True

    def check_fractional_service(self, instance, response):
        if response and response['is_registered'] == 'Y':
            if response['auto_switch_to_int'] != 'Y':
                instance.change_status(get_contract_status(type='KRW_margin_apply_wait'))
                return True
            raise PreconditionFailed()

    def check_margin_usable_kr(self, instance, response):
        if response and int(response['grid_cnt']):
            record = response['records'][-1]

            if record['register_date'] and not record['cancel_date']:
                instance.change_status(get_contract_status(type='KRW_margin_apply_success'))
                return True

    def to_representation(self, instance):
        vendor_code = instance.vendor.vendor_props.code
        request = self.context['request']
        response_check = True

        if instance.status.code == get_contract_status(type='vendor_wait_account_id_card', code=True):
            endpoint = '/api/v1/{}/account'.format(vendor_code)
            def_name = 'account'
        elif instance.status.code in [
            get_contract_status(type='vendor_contract_transaction_limit_wait', code=True),
            get_contract_status(type='vendor_contract_transaction_limit_fail', code=True)
        ]:
            if 'status' not in request.GET:
                raise PreconditionFailed(detail='The vendor_contract_transaction_limit status need status field.')
            instance.change_status(ContractStatus.objects.get(code=request.GET['status']))
            response_check = False
        elif instance.status.code == get_contract_status(type='fractional_share_trading_waiting', code=True):
            endpoint = '/api/v1/{}/account/fractional/service/status'.format(vendor_code)
            def_name = 'fractional_service'
        elif instance.status.code == get_contract_status(type='KRW_margin_apply_wait', code=True):
            endpoint = '/api/v1/{}/account/margin/usable/kr'.format(vendor_code)
            def_name = 'margin_usable_kr'
        elif instance.status.code == get_contract_status(type='KRW_margin_apply_success', code=True):
            instance.change_status(ContractStatus.objects.get(type='bp_fee_st_reg_wait'))
            response_check = False
        elif instance.status.code == get_contract_status(type='bp_fee_st_reg_wait', code=True):
            response_check = False
        else:
            raise PreconditionFailed(detail={
                'status': ContractStatus.objects.get(code=instance.status.code).name,
                'message': 'The Contract status not available.'
            })

        if response_check:
            response = instance.get_realtime_data('realtime', endpoint)
            getattr(self, 'check_{}'.format(def_name))(instance, response)

        output_serializer = SyncStatusRespSerializer(instance=instance)
        return output_serializer.data


class SyncStatusRespSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ('id', 'status', 'account_number', 'account_alias', 'contract_number')
        extra_kwargs = {
            'status': {'read_only': True, },
            'account_number': {'read_only': True, },
            'account_alias': {'read_only': True, }
        }


class OpenAccountStatusReqSerializer(serializers.Serializer):
    data = serializers.CharField(help_text="암호화 데이터")

    def get_decrypted_data(self, instance, data):
        vendor_code = instance.vendor.vendor_props.code

        if data.get('data'):
            key = AES_KEY.get(vendor_code.upper()).encode()
            aes = Aes(key)
            return aes.decrypt(data.get('data'))
        raise PreconditionFailed(detail='Data must not be null.')

    def change_open_account_status(self, instance, data):
        decrypted_data = data.split('|')

        try:
            account_status = decrypted_data[4]
        except IndexError as e:
            raise PreconditionFailed(detail=e)

        if account_status == AccountStatusChoices.ACCOUNT_STATUS.skiped:
            instance.change_status(get_contract_status(type='vendor_wait_account_id_card'))
        elif account_status == AccountStatusChoices.ACCOUNT_STATUS.completed:

            try:
                instance.account_number = decrypted_data[5] + '010'
                instance.account_alias = decrypted_data[6] + '010'
                instance.status = get_contract_status(type='vendor_account_success')
                instance.save()
            except IndexError as e:
                raise PreconditionFailed(detail=e)

            output_serializer = OrderProxyRegisterSerializer(instance=instance)
            output_serializer.update(instance, data)
        else:
            raise PreconditionFailed(detail="Invalid status : {}".format(account_status))

        return instance
