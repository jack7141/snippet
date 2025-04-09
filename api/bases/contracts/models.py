import ast
import json
import uuid
import requests
import logging
import pandas as pd

from urllib.parse import urljoin
from json import JSONDecodeError

from dateutil.relativedelta import relativedelta

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

from model_utils.fields import StatusField
from auditlog.registry import auditlog
from fernet_fields import EncryptedCharField, EncryptedTextField

from common.behaviors import UniqueTimestampable
from common.decorators import cached_property

from api.bases.notifications.models import Notification
from api.bases.funds.models import Operation
from api.bases.funds.utils import BDay
from api.bases.etf_kr.models import Profile
from api.bases.etf_us.models import Profile as USProfile

from api.bases.contracts.adapters import fep_adapter
from api.bases.contracts.choices import (
    ContractChoices,
    ContractTypeChoices,
    TermDetailChoices,
    ConditionChoices,
    RebalancingQueueChoices,
    ReservedActionChoices,
    TransferChoices
)

logger = logging.getLogger('django.server')

MAXIMUM_PAYMENT_LIMIT = 18000000

FEP_API_BACKEND = settings.FEP_API_BACKEND
FEP_HANAW_API_BACKEND = settings.FEP_HANAW_API_BACKEND
ACCOUNT_MULTIPLE_DUE_DAY = settings.ACCOUNT_MULTIPLE_DUE_DAY


def create_contract_number():
    count = Contract.objects.filter(
        created_at__gte=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count() + 1
    return '{0}{1:06d}'.format(timezone.now().strftime('%Y%m%d%H%M%S'), count)


def validate_file_extension(value):
    import os
    from django.core.exceptions import ValidationError
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    valid_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.png']
    if not ext.lower() in valid_extensions:
        raise ValidationError(u'Unsupported file extension.')


def get_contract_status(type, code=None):
    contract_status = ContractStatus.objects.get(type=type)
    if code:
        return contract_status.code
    return contract_status


class ContractManager(models.Manager):
    def get_active_contracts(self, contract_type=None):
        queryset = self.get_base_queryset(contract_type)
        return queryset.filter(status=get_contract_status(type='normal'))

    def get_available_cancel_contracts(self):
        return self.filter(status=get_contract_status(type='vendor_wait_cancel'))

    def get_base_queryset(self, contract_type=None):
        queryset = self.prefetch_related('orders').filter(is_canceled=False,
                                                          status=get_contract_status(type='normal'))
        if contract_type:
            queryset = queryset.filter(contract_type=contract_type)

        return queryset

    def get_rebalancing_contracts(self, contract_type=None):
        queryset = self.get_base_queryset(contract_type)
        queryset = queryset.filter(id__in=[item.id for item in queryset if (item.reb_required or
                                                                            item.is_available_reb)])
        return queryset

    def get_reb_required_only(self, contract_type=None):
        queryset = self.get_base_queryset(contract_type)
        return queryset.filter(id__in=[item.id for item in queryset if item.reb_required])

    def get_reb_notify_only(self, contract_type):
        queryset = self.get_base_queryset(contract_type)
        return queryset.filter(id__in=[item.id for item in queryset if (item.reb_required and item.check_for_notify)])

    def get_latest_account_open_contract(self):
        filter_kwargs = {
            "acct_completed_at__gte": timezone.now() - BDay(ACCOUNT_MULTIPLE_DUE_DAY)
        }
        return self.filter(acct_completed_at__isnull=False, **filter_kwargs)

    def get_advisory_contracts(self):
        queryset = self.get_base_queryset()
        return queryset.filter(contract_type__operation_type=ContractTypeChoices.OPERATION_TYPE.A)

    def get_discretionary_contracts(self):
        queryset = self.get_base_queryset()
        return queryset.filter(contract_type__operation_type=ContractTypeChoices.OPERATION_TYPE.D)


class TermDetailManager(models.Manager):

    def get_term_detail(self, contract_type, pk=None):
        """
        약관 상세 내역 지정 조건

        * pk를 입력한 경우
        * -> pk에 해당하는 상세 내역 반환
        * pk를 입력하지 않은 경우
        * -> contract_type 중 is_default에 해당하는 마지막 계약 약관 상세 내역 반환

        :param contract_type: 계약 타입 코드
        :param pk: primary key
        :return instance: TermDetail
        """
        queryset = self.get_queryset().filter(term__contract_type=contract_type)
        return queryset.get(pk=pk) if pk else queryset.filter(is_default=True).last()


REALTIME_ASSET_CATEGORY_MAPPER = {
    '해외주식': 'FS',
    '국내주식': 'DS',
    '해외채권': 'FB',
    '국내채권': 'DB'
}


class ContractType(models.Model):
    code = models.CharField(max_length=4, primary_key=True, blank=False, null=False, help_text='관리코드')
    name = models.CharField(max_length=40, blank=False, null=False, help_text='계약명')
    operation_type = models.CharField(max_length=1, choices=ContractTypeChoices.OPERATION_TYPE, blank=False, null=False,
                                      default=ContractTypeChoices.OPERATION_TYPE.A, help_text='자문/일임 구분')
    universe = models.IntegerField(blank=False, null=False, help_text='유니버스 코드')
    asset_type = models.CharField(choices=ContractTypeChoices.ASSET_TYPE, max_length=8, blank=False, null=False,
                                  help_text='상품에 포함 자산 종류 구분')
    description = models.TextField(null=True, blank=True, help_text='계약 종류 설명')
    is_orderable = models.BooleanField(default=False, help_text='주문 가능 유무')
    fixed_risk_type = models.BooleanField(default=False, help_text='위험성향 변경 가능 유무')
    is_bankingplus = models.BooleanField(default=False, help_text='뱅킹플러스 사용 유무')
    fee_type = models.IntegerField(choices=ContractTypeChoices.FEE_TYPE, blank=False, null=False, help_text='보수 종류')
    reb_interval = models.IntegerField(default=90, blank=False, null=False, help_text='리밸런싱 발생 간격 일 수')
    resend_interval = models.IntegerField(default=5, blank=False, null=False, help_text='재전송 기준일 수')
    delay_interval = models.IntegerField(default=0, blank=False, null=False, help_text='지연실행 기준일 수')
    date_method = models.IntegerField(choices=ContractTypeChoices.DATE_METHOD,
                                      default=ContractTypeChoices.DATE_METHOD.default, help_text='일수 계산 방식')
    fee_period = models.IntegerField(choices=ContractTypeChoices.FEE_PERIOD, default=1, help_text='수수료 수취 기간 단위')

    def __str__(self):
        return '{}({})'.format(self.name, self.code)

    def __eq__(self, other):
        if isinstance(other, str):
            return self.code == other
        else:
            return super().__eq__(other)

    def interval_datetime(self, interval):
        date_method = self.date_method

        if date_method == ContractTypeChoices.DATE_METHOD.default:
            return relativedelta(days=interval)
        elif date_method == ContractTypeChoices.DATE_METHOD.business:
            return BDay(interval)

    @cached_property
    def reb_interval_value(self):
        return self.interval_datetime(self.reb_interval)

    @cached_property
    def resend_interval_value(self):
        return self.interval_datetime(self.resend_interval)

    @cached_property
    def delay_interval_value(self):
        return self.interval_datetime(self.delay_interval)


class ContractStatus(models.Model):
    category = models.CharField(max_length=40, blank=False, null=False, default='Default', help_text='계약 상태 카테고리')
    code = models.IntegerField(primary_key=True, blank=False, null=False, default=41, help_text='계약 상태 코드')
    type = models.CharField(max_length=40, unique=True, blank=False, null=False, default='vendor_wait_account',
                            help_text='계약 상태 타입')
    name = models.CharField(max_length=40, blank=False, null=False, default='협력사 계좌개설 대기', help_text='계약 상태명')

    class Meta:
        verbose_name_plural = "Contract status"

    def __str__(self):
        return self.name


class Term(UniqueTimestampable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=128, blank=False, null=False, unique=True, help_text='조건 이름')
    field_1 = models.CharField(max_length=128, blank=True, null=True)
    field_2 = models.CharField(max_length=128, blank=True, null=True)
    field_3 = models.CharField(max_length=128, blank=True, null=True)
    field_4 = models.CharField(max_length=128, blank=True, null=True)
    field_5 = models.CharField(max_length=128, blank=True, null=True)
    field_6 = models.CharField(max_length=128, blank=True, null=True)
    field_7 = models.CharField(max_length=128, blank=True, null=True)
    field_8 = models.CharField(max_length=128, blank=True, null=True)
    field_9 = models.CharField(max_length=128, blank=True, null=True)
    field_10 = models.CharField(max_length=128, blank=True, null=True)
    contract_file = models.FileField(upload_to='contracts/%Y%m%d', validators=[validate_file_extension],
                                     blank=True, null=True, help_text='계약서 파일')
    appendix_file_1 = models.FileField(upload_to='contracts/%Y%m%d/appendix', validators=[validate_file_extension],
                                       blank=True, null=True, help_text='별첨 파일 1')
    appendix_file_2 = models.FileField(upload_to='contracts/%Y%m%d/appendix', validators=[validate_file_extension],
                                       blank=True, null=True, help_text='별첨 파일 2')
    appendix_file_3 = models.FileField(upload_to='contracts/%Y%m%d/appendix', validators=[validate_file_extension],
                                       blank=True, null=True, help_text='별첨 파일 3')
    is_default = models.BooleanField(default=False, help_text='기본 계약 조건 여부')
    is_publish = models.BooleanField(default=False, help_text='발행 여부')
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')
    contract_type = models.ForeignKey(ContractType, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name='contract_type', db_column='contract_type', help_text='계약종류')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.contract_type and self.is_default:
            try:
                temp = Term.objects.filter(contract_type=self.contract_type).get(is_default=True)
                if self != temp:
                    temp.is_default = False
                    temp.save()
            except Term.DoesNotExist:
                pass
        super(Term, self).save(*args, **kwargs)


class TermDetail(models.Model):
    """
    * is_static: 무료 적용 시작 기준일(True: 약관 적용일, False: TermDetail 생성일)
    """
    objects = TermDetailManager()
    title = models.CharField(max_length=32, null=False, blank=False, help_text='수수료 적용 조건명')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, help_text='계약 약관')
    amount = models.IntegerField(default=0, null=True, blank=True, validators=[MinValueValidator(0)], help_text='수수료액')
    rate = models.FloatField(default=0, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(1)],
                             help_text='수수료율')
    min_max = models.IntegerField(choices=TermDetailChoices.MIN_MAX, default=1, help_text='최소, 최대 구분')
    effective_date = models.DateField(null=True, blank=True, help_text='약관 적용 일자')
    is_free = models.BooleanField(default=False, help_text='무료 적용 여부')
    period_int = models.IntegerField(default=0, null=True, blank=True, validators=[MinValueValidator(0)],
                                     help_text='무료 적용 기간(정수)')
    period_type = models.IntegerField(choices=TermDetailChoices.PERIOD_TYPE, default=3, help_text='무료 적용 기간(단위)')
    is_static = models.BooleanField(default=True, help_text='기준일 고정 여부')
    is_default = models.BooleanField(default=False, help_text='기본 수수료 조건 여부')
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')

    class Meta:
        db_table = 'term_detail'

    def __str__(self):
        return f'{self.term.title}_{self.title}'

    def save(self, *args, **kwargs):
        if self.term.contract_type and self.is_default:
            try:
                temp = TermDetail.objects.filter(term__contract_type=self.term.contract_type,
                                                 term__field_1=self.term.field_1).get(is_default=True)
                if self != temp:
                    temp.is_default = False
                    temp.save()
            except TermDetail.DoesNotExist:
                pass
        super(TermDetail, self).save(*args, **kwargs)


class Contract(models.Model):
    objects = ContractManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True, help_text="계약 UUID")
    contract_number = models.CharField(max_length=20, default=create_contract_number, editable=False, help_text="계약 번호")
    contract_type = models.ForeignKey(ContractType, on_delete=models.PROTECT, null=False, blank=False,
                                      related_name='contracts', db_column='contract_type', help_text='계약종류')
    account_number = EncryptedCharField(max_length=128, default=create_contract_number, blank=False, null=False,
                                        help_text="계좌번호")
    account_alias = models.CharField(max_length=128, default=create_contract_number, blank=False, null=False,
                                     help_text="계좌대체번호", unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, help_text='계약자')
    risk_type = models.IntegerField(null=True, blank=False, help_text="위험 성향")
    vendor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, help_text='증권사',
                               related_name='vendor')
    term = models.ForeignKey(Term, on_delete=models.PROTECT, help_text='계약 약관 조건', null=False, blank=False,
                             related_name='term')
    status = models.ForeignKey(ContractStatus, on_delete=models.PROTECT, null=False, blank=False,
                               related_name='contracts', db_column='status', help_text='계약 상태')
    firm_agreement_at = models.DateTimeField(null=True, blank=True, help_text='출금이체 동의 날짜', editable=False)
    acct_completed_at = models.DateTimeField(null=True, blank=True, help_text='계좌생성 완료 날짜', editable=False)
    created_at = models.DateTimeField(auto_now_add=True, help_text='계약 체결일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')
    canceled_at = models.DateTimeField(null=True, blank=True, help_text='해지일', editable=False)
    rebalancing = models.BooleanField(default=False, help_text='리밸런싱 발생 여부')
    is_canceled = models.BooleanField(default=False, help_text="계약 취소 여부")
    cancel_reason = models.CharField(max_length=128, blank=True, null=True, help_text='계약 취소 사유')
    term_detail = models.ForeignKey(TermDetail, null=True, blank=True, help_text='약관 상세 조건')

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return '{}({})'.format(self.contract_number, self.contract_type)

    def save(self, *args, **kwargs):
        try:
            # TODO: account_number, account_alias 기본값 정리 필요.
            if self.created_at is None:
                self.account_number = self.account_alias = self.contract_number
        except Exception as e:
            logger.error(e)

        return super().save(*args, **kwargs)

    def change_status(self, status):
        self.status = status
        self.save()

    def change_risk_type(self, risk_type, force_update=False):
        if self.risk_type is None:
            return self

        if force_update:
            self.risk_type = risk_type
        elif self.risk_type > risk_type:
            self.risk_type = risk_type

        self.save()

    def get_reb_interval(self, contract_type=None):
        return self.contract_type.reb_interval_value

    def get_next_order_mode(self):
        if not self.reb_required:
            return None

        mode = ContractChoices.ORDER_MODES.rebalancing

        if self.contract_type == 'EA':
            if self.last_order.mode == ContractChoices.ORDER_MODES.sell and \
                    self.last_order.status \
                    in [ContractChoices.ORDER_STATUS.completed, ContractChoices.ORDER_STATUS.skipped]:
                mode = ContractChoices.ORDER_MODES.buy
            else:
                mode = ContractChoices.ORDER_MODES.sell
        return mode

    def check_available_buy(self):
        return bool(self.last_order and
                    self.last_order.mode == ContractChoices.ORDER_MODES.sell and
                    self.last_order.status
                    in [ContractChoices.ORDER_STATUS.completed, ContractChoices.ORDER_STATUS.skipped])

    def check_available_rebalancing(self):
        interval = self.get_reb_interval()
        return bool(self.last_order and self.last_order.completed_at and
                    (self.last_order.completed_at + interval < timezone.now()))

    def check_for_notify(self):
        now = timezone.now()
        interval = self.contract_type.resend_interval_value

        if self.last_order and \
                self.last_order.completed_at and \
                self.last_order.mode == ContractChoices.ORDER_MODES.sell:
            target_date = self.last_order.completed_at + interval
            return bool(self.last_order and self.last_order.completed_at and (target_date >= now))
        else:
            reb_notices = self.rebs.latest('created_at') \
                .notifications.filter(message__icontains='리밸런싱 발생', protocol=1)

            return bool(self.last_order and
                        not reb_notices.exists() or
                        reb_notices.earliest('created_at').created_at + interval >= now)

    @cached_property
    def last_order(self):
        try:
            return self.orders.all()[0]
        except:
            return self.orders.latest('created_at')

    @cached_property
    def last_transfer(self):
        try:
            return self.transfer.filter(is_canceled=False).all()[0]
        except:
            return self.transfer.filter(is_canceled=False).latest('created_at')

    @cached_property
    def last_reb(self):
        try:
            return self.rebs.all().order_by('-created_at').all()[0]
        except:
            return self.rebs.latest('created_at')

    @cached_property
    def effective_date(self):
        first_order = self.orders.earliest('created_at')
        if first_order is None:
            return first_order
        return first_order.created_at.astimezone().date()

    @cached_property
    def is_available_reb(self):
        interval = self.get_reb_interval()
        return bool(self.last_order and self.last_order.completed_at and
                    self.last_order.completed_at + interval <= timezone.now())

    @cached_property
    def check_condition(self):
        return bool(self.last_order and
                    self.last_order.status == ContractChoices.ORDER_STATUS.completed and
                    not self.reb_status)

    @property
    def reb_required(self):
        return (self.last_order and self.last_order.mode == ContractChoices.ORDER_MODES.sell) \
            or self.rebalancing

    @property
    def reb_status(self):
        if not self.reb_required:
            return None

        if self.check_available_buy():
            return {'mode': ContractChoices.ORDER_MODES.buy, 'status': ContractChoices.ORDER_STATUS.on_hold}
        elif self.last_order.mode in [ContractChoices.ORDER_MODES.new_order,
                                      ContractChoices.ORDER_MODES.rebalancing,
                                      ContractChoices.ORDER_MODES.buy]:
            return None

        return {'mode': self.last_order.mode, 'status': self.last_order.status}

    @cached_property
    def next_rebalancing(self):
        order_queryset = self.orders.filter(mode=ContractChoices.ORDER_MODES.new_order, completed_at__isnull=False,
                                            status=ContractChoices.ORDER_STATUS.completed)
        has_rebs = self.rebs.exists()
        has_orders = order_queryset.exists()
        next_reb = None
        if not has_rebs and not has_orders:
            return next_reb

        if has_rebs:
            last_reb = self.rebs.latest('created_at')
            if last_reb.sold_at and last_reb.bought_at:
                # 마지막 매수일 + 리밸런싱 주기
                next_reb = last_reb.bought_at + self.get_reb_interval()
        elif has_orders:
            # 마지막 신규주문 완료일 + 리밸런싱 주기
            completed_new_order = order_queryset.get()
            next_reb = completed_new_order.completed_at + self.get_reb_interval()

        if not next_reb:
            return next_reb
        elif next_reb.astimezone().hour > 11:
            next_reb += relativedelta(days=1)

        return next_reb.astimezone().replace(hour=11, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    def get_assets(self):
        try:
            if settings.USE_REALTIME:
                return self.realtime_asset.get('list')
            else:
                if self.assets.exists():
                    return self.asset_detail.filter(created_at=self.assets.latest('created_at').created_at)
                else:
                    return None
        except:
            return None

    # Note: get_stored_asset_details, get_stored_asset 특정 시간에 자산 데이터 오류있는경우 사용
    @cached_property
    def get_stored_asset_details(self):
        if self.assets.exists():
            return self.asset_detail.filter(created_at=self.assets.latest('created_at').created_at)
        else:
            return None

    @cached_property
    def get_stored_asset(self):
        return self.assets.latest('created_at')

    def get_realtime_data(self, field_name, endpoint, method="POST", *args, **kwargs):
        setattr(self, field_name, None)

        # KB 계좌개설 내재화로 채번전 API 호출 가능
        if self.status.code == get_contract_status(type='vendor_wait_account', code=True) and \
                self.vendor.vendor_props.code == 'kb':
            pass
        elif (self.account_number == self.account_alias and self.vendor.vendor_props.code != 'hanaw') or \
                self.status.code == get_contract_status(type='vendor_wait_account', code=True):
            return None

        url = urljoin(FEP_API_BACKEND, endpoint)
        if self.vendor.vendor_props.code == 'hanaw':
            url = urljoin(FEP_HANAW_API_BACKEND, endpoint)

        response = fep_adapter.get_vendor_data(self.vendor.vendor_props.code,
                                               url,
                                               self.account_number,
                                               self.account_alias,
                                               self.user.profile.ci,
                                               method,
                                               **kwargs)

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

    @cached_property
    def get_latest_asset_with_update(self):
        try:
            _cache = cache.get(f'cache.contract-detail-{str(self.id)}')

            # Note. 2.9.x 앱 버전에서 CMA 상세페이지 접근시 데이터 갱신하지 않음. 서버에서 직접 갱신처리함.
            if self.contract_type.code == 'CMA':
                _cache = None

            if _cache is None and settings.USE_REALTIME:
                return self.realtime_asset
            elif _cache:
                return _cache
            else:
                return self.assets.latest('created_at')
        except:
            return None

    @cached_property
    def get_latest_asset(self):
        try:
            if settings.USE_REALTIME:
                return self.realtime_asset
            else:
                return self.assets.latest('created_at')
        except:
            return None

    def get_previous_asset(self):
        try:
            return self.assets.latest('created_at').get_previous_by_created_at(account_alias=self.account_alias)
        except self.assets.model.DoesNotExist:
            return None

    @cached_property
    def realtime_asset(self):
        if self.account_number == self.account_alias or \
                self.status.code == get_contract_status(type='vendor_wait_account', code=True):
            return None

        headers = {'Content-Type': "application/json"}
        fep_api_backend = FEP_API_BACKEND
        if self.vendor.vendor_props.code == 'hanaw':
            fep_api_backend = FEP_HANAW_API_BACKEND

        url = urljoin(fep_api_backend, '/api/v1/{}/account/acct-balance'.format(self.vendor.vendor_props.code))
        response = requests.request("POST", url,
                                    headers=headers,
                                    json={
                                        'acct_no': self.account_number,
                                        'account_alias': self.account_alias,
                                        'ci_valu': self.user.profile.ci
                                    })

        ret = response.json()
        body = ret.get('dataBody')
        if body:
            contract_type = self.contract_type
            asset_lists = body.get('list')
            asset_lists = asset_lists if asset_lists else []

            for item in asset_lists:
                try:
                    if contract_type.asset_type == 'kr_fund':
                        item.update({'asset': Operation.objects.get(symbol=item.get('inves_soct_fund_code'),
                                                                    end_date__isnull=True)})
                    elif contract_type.asset_type == 'kr_etf':
                        asset = Profile.objects.get(symbol=item.get('stbd_code')[1:])
                        item.update({'asset': asset})
                        item.update({'inves_soct_fund_code': asset.isin})
                    elif contract_type.asset_type == 'etf':
                        asset = USProfile.objects.get(symbol=item.get('stbd_code'))
                        item.update({'asset': asset})
                        item.update({'inves_soct_fund_code': asset.isin})
                except:
                    item.update({
                        'asset': {'name': item.get('stbd_nm'),
                                  'get_asset_category': REALTIME_ASSET_CATEGORY_MAPPER.get(
                                      item.get('wms_asst_type_nm'))},
                        'inves_soct_fund_code': item.get('stbd_code'),
                    })
            try:
                # 자산정보 15분 기준으로 업데이트 처리, Cache 처리
                cache.set(f'cache.contract-detail-{str(self.id)}', body, timeout=15 * 60)
            except Exception as e:
                pass
            return body
        return None

    @cached_property
    def assets_history_df(self):
        df = pd.DataFrame(self.assets.values('base', 'deposit', 'balance', 'prev_deposit', 'created_at'))
        try:
            df = df[df['created_at'] <= timezone.localtime() - relativedelta(days=1)]
        except:
            pass

        df['base'] = df['base'].mask(df['base'] < 0, 0)
        df['date'] = pd.to_datetime(df['created_at'])
        df = df.set_index('date')
        return df


class Condition(models.Model):
    contract = models.OneToOneField(Contract, on_delete=models.CASCADE, primary_key=True)
    period_year = models.PositiveSmallIntegerField(blank=False, null=False, validators=[MinValueValidator(5)],
                                                   help_text='가입 기간')
    expired_at = models.DateTimeField(blank=False, null=False, help_text='가입 만기일')
    received_at = models.DateTimeField(blank=True, null=True, help_text='수령개시 희망일(연금)')

    payment_limit = models.IntegerField(blank=True, null=True, validators=[MaxValueValidator(MAXIMUM_PAYMENT_LIMIT)],
                                        help_text='납입 한도')
    set_limit = models.IntegerField(blank=True, null=True, validators=[MaxValueValidator(MAXIMUM_PAYMENT_LIMIT)],
                                    help_text='설정 한도')

    tr_amount = models.PositiveIntegerField(blank=True, null=True, help_text='자동이체 월 납부금')
    tr_reg_date = models.PositiveIntegerField(choices=ConditionChoices.REG_DATE, blank=True, null=True,
                                              help_text='자동이체 처리일')
    tr_expired_at = models.DateTimeField(blank=True, null=True, help_text='월 납부 이체 기간')
    sign = EncryptedTextField(blank=True, null=True, help_text='서명 정보 Base64')
    volume_path = models.CharField(blank=True, null=True, max_length=128, help_text='증권사 계약 문서 저장 볼륨')
    doc_path = models.CharField(blank=True, null=True, max_length=128, help_text='증권사 계약 문서 경로')
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')

    def __str__(self):
        return str(self.contract)


class Extra(models.Model):
    contract = models.OneToOneField(Contract, on_delete=models.CASCADE, primary_key=True)
    label = models.CharField(null=True, blank=True, max_length=64, help_text='구분')
    target_date = models.DateTimeField(blank=True, null=True, help_text='목표 설정일')
    catalog_id = models.IntegerField(blank=True, null=True, help_text='가입 상품 ID')
    strategy_code = models.IntegerField(blank=True, null=True, help_text='운영 전략 코드')
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')


class Rebalancing(UniqueTimestampable):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='rebs', help_text='계약')
    sold_at = models.DateTimeField(blank=True, null=True, help_text='매도일')
    bought_at = models.DateTimeField(blank=True, null=True, help_text='매수일')
    note = models.CharField(max_length=128, blank=True, null=True, help_text='기타 사항')
    notifications = models.ManyToManyField(Notification, related_name='rebs', help_text='알람 발생 목록')


class RebalancingQueue(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="reb_requests", help_text="계약")
    status = models.IntegerField(choices=RebalancingQueueChoices.STATUS, help_text="상태")
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')
    completed_at = models.DateTimeField(blank=True, null=True, help_text="완료일")

    def complete(self):
        self.status = RebalancingQueueChoices.STATUS.completed
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])


class ProvisionalContract(models.Model):
    ACCOUNT_OPEN_STEP_ID = "account_open"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True, help_text="임시 계약 UUID")
    account_alias = models.CharField(max_length=128, blank=True, null=True, help_text="임시계좌번호")
    contract_type = models.ForeignKey(ContractType, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name='provisionals', db_column='contract_type', help_text='임시 계약종류')
    step = EncryptedTextField(blank=True, null=True, help_text='진행상태 구분')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, help_text='계약자')
    is_contract = models.BooleanField(default=False, help_text='계약 해지 여부')
    created_at = models.DateTimeField(auto_now_add=True, help_text='임시 계약 체결일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')
    contract = models.OneToOneField(Contract, on_delete=models.CASCADE, blank=True, null=True,
                                    related_name='provisional')

    class Meta:
        db_table = 'contracts_provisional'

    def __str__(self):
        try:
            return '{} - {}|{}'.format(str(self.id), self.account_alias, self.contract_type)
        except:
            return self

    def load_step(self, step_id=None):
        """
        임시 계약에서 사용 되는 json 필드
        값이 없을 경우 초기화
        """
        if self.step:
            try:
                step = json.loads(str(self.step))
            except JSONDecodeError:
                step = ast.literal_eval(str(self.step))

            try:
                if step_id:
                    step = step.get(step_id, {})
            except (TypeError, AttributeError):
                return step
            return step
        else:
            return {}

    def update_step(self, step_id, *args, **kwargs):
        """
        json step 업데이트
        값이 없을 경우 초기화
        """
        step = self.load_step()
        try:
            current_step = step[step_id]
            current_step.update(kwargs)
            self.step = step
        except (TypeError, KeyError, AttributeError):
            step = {}
            step[step_id] = kwargs
            self.step = step
        return json.dumps(self.step)


class ReservedAction(UniqueTimestampable):
    STATUS = ReservedActionChoices.STATUS
    ACTIONS = ReservedActionChoices.ACTIONS

    start_at = models.DateTimeField(null=False, blank=False, help_text='예약실행 시작일')
    status = StatusField(default=STATUS.reserved, help_text='실행 상태')
    action = StatusField(choices_name='ACTIONS', help_text='실행 종류')
    contract = models.ForeignKey(Contract, blank=False, null=True, on_delete=models.SET_NULL,
                                 related_name='reserved_actions', help_text='계약')
    register = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, help_text='등록자',
                                 editable=False)
    task_id = models.UUIDField(null=True, blank=True, editable=False, help_text='실행된 task')

    def __str__(self):
        try:
            if self.contract:
                return '{}({})'.format(self.action, self.contract.contract_number)
            else:
                return '{}'.format(self.action)
        except:
            return str(self.id)

    class Meta:
        db_table = 'contracts_reserved_action'


class Assets(models.Model):
    account_alias = models.ForeignKey(Contract, to_field='account_alias', on_delete=models.CASCADE,
                                      related_name='assets')
    base = models.IntegerField()
    deposit = models.IntegerField()
    balance = models.IntegerField()
    prev_deposit = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')

    class Meta:
        db_table = 'contracts_assets'
        unique_together = (('account_alias', 'created_at'),)


class AssetsDetail(models.Model):
    account_alias = models.ForeignKey(Contract, to_field='account_alias', on_delete=models.CASCADE,
                                      related_name='asset_detail')
    code = models.CharField(max_length=12, help_text='ISIN')
    buy_price = models.DecimalField(max_digits=20, decimal_places=5, help_text='구매가')
    shares = models.IntegerField(help_text='좌수')
    balance = models.DecimalField(max_digits=20, decimal_places=5, help_text='평가금액')
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')

    class Meta:
        db_table = 'contracts_assets_detail'
        unique_together = (('account_alias', 'code', 'created_at'),)

    @cached_property
    def asset(self):
        contract_type = self.account_alias.contract_type

        try:
            if contract_type.asset_type == 'kr_fund':
                return Operation.objects.get(symbol=self.code, end_date__isnull=True)
            elif contract_type.asset_type == 'kr_etf':
                return Profile.objects.filter(isin__contains=self.code).last()
            elif contract_type.asset_type == 'etf':
                return USProfile.objects.get(symbol=self.code)
            return None
        except:
            return None


class Transfer(UniqueTimestampable):
    status = models.IntegerField(choices=TransferChoices.STATUS, default=TransferChoices.STATUS.transfer_in_progress,
                                 help_text='이전 상태')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='transfer', help_text='계약')
    account_number = EncryptedCharField(max_length=128, blank=False, null=False, help_text="상대 계좌번호")
    product_type = models.CharField(choices=TransferChoices.PRODUCT_TYPE, max_length=10, default=None, null=True,
                                    help_text='상대 계좌 타입')
    vendor = models.CharField(max_length=100, blank=True, null=True, help_text='상대 기관 및 지점명')
    company = models.CharField(max_length=20, blank=True, null=True, help_text='기관명')
    company_code = models.CharField(max_length=10, blank=True, null=True, help_text='기관코드')
    completed_at = models.DateTimeField(null=True, default=None, help_text='이전 완료일')
    is_canceled = models.BooleanField(default=False, help_text='계약 이전 취소')
    canceled_at = models.DateTimeField(null=True, blank=True, help_text='해지일', editable=False)

    def __str__(self):
        return '{}({})'.format(self.account_number, self.vendor)

    @cached_property
    def is_available_cancel(self):
        return bool(self.status != TransferChoices.STATUS.transfer_in_progress)

    def save(self, *args, **kwargs):
        if self.status == TransferChoices.STATUS.transfer_done and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)


auditlog.register(Contract)
auditlog.register(ReservedAction)
auditlog.register(Rebalancing)
auditlog.register(Term)
auditlog.register(TermDetail)
auditlog.register(Transfer)
