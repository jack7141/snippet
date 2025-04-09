import logging
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytz
import requests as req
from django.conf import settings
from django.db import models
from django.utils import timezone
from fernet_fields import EncryptedCharField
from model_utils import Choices

from api.bases.accounts.calcuator import BaseAmountCalculator, CheckBaseAmountCalculator
from api.bases.accounts.managers import TradeQuerySet, ExecutionQuerySet, HoldingQuerySet, AccountDetectionManger
from common.behaviors import Timestampable
from common.decorators import reversion_diff
from common.exceptions import PreconditionFailed
from common.utils import gen_choice_desc, get_datetime_kst, convert_datetime_kst

logger = logging.getLogger('django.server')


def create_account_alias():
    return timezone.now().strftime('%Y%m%d%H%M%S%f')


class Account(Timestampable, models.Model, AccountDetectionManger):
    TYPE = Choices(
                    (0, 'general', '종합위탁계좌'),
                    ('cma', [
                            (1, 'cma_rp', '환매조건부 채권'),
                            (11, 'cma_mmf', '단기금융펀드'),
                            (12, 'cma_mmw', '랩어카운트'),
                            ]),
                    ('pension', [
                                (2, 'pension_saving', '연금 저축'),
                                (21, 'pension_irp', '연금 IRP'),
                                ]),
                     )

    OWNER = Choices(('personal', '개인'),
                    ('corporate', '법인'))

    ACCOUNT_TYPE = Choices(('kr_fund', '국내 펀드'),
                           ('kr_etf', '국내 ETF'),
                           ('etf', '해외 ETF'))

    RISK_TYPE = Choices(
        (0, 'VERY_LOW', '초저위험'),
        (1, 'LOW', '저위험'),
        (2, 'MID', '중위험'),
        (3, 'HIGH', '고위험'),
        (4, 'VERY_HIGH', '초고위험'),
    )

    STATUS = Choices(
        (0, 'canceled', '해지됨'),
        (1, 'normal', '정상 유지'),
        (22, 'account_sell_reg', '해지 매도 진행 중'),
        (23, 'account_sell_f1', '해지 매도 실패'),
        (24, 'account_sell_s', '해지 매도 완료'),
        (25, 'account_exchange_reg', '환전 진행 중'),
        (26, 'account_exchange_f1', '환전 실패'),
        (27, 'account_exchange_s', '환전 완료'),
        ('suspension', [
            (3, 'account_suspension', '운용 중지'),
            (30, 'accident_suspension', '이상 계좌 중지'),
            (31, 'unsupported_suspension', '미지원 종목 보유 운용 중지'),
            (32, 'base_amount_suspension', '최소 원금 위반 중지'),
            (33, 'trade_suspension', '임의 거래 중지'),
            (34, 'risk_type_suspension', '투자 성향 안정형 운용 중지'),
        ])
    )

    account_alias = models.CharField(primary_key=True, default=create_account_alias, max_length=128,
                                     help_text="계좌번호 별칭(INDEX)")
    vendor_code = models.CharField(null=False, max_length=8, help_text="증권사구분")
    account_number = EncryptedCharField(null=False, max_length=128, help_text="계좌번호(암호화필수)")
    account_type = models.CharField(choices=ACCOUNT_TYPE, max_length=8, blank=False, null=False,
                                    help_text=gen_choice_desc('자산 구분', ACCOUNT_TYPE))
    type = models.IntegerField(choices=TYPE, default=TYPE.general, help_text='계좌 구분')
    owner_type = models.CharField(choices=OWNER, default=OWNER.personal, max_length=12, blank=False, null=False,
                                    help_text=gen_choice_desc('소유 구분', OWNER))
    status = models.IntegerField(choices=STATUS, default=STATUS.normal, help_text='계약 상태')
    risk_type = models.IntegerField(choices=RISK_TYPE, null=True, blank=True, help_text="투자성향")
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False, default=None, help_text="삭제 요청 일자")
    strategy_code = models.IntegerField(help_text="전략 구분", default=0, null=False)
    order_setting = models.ForeignKey('orders.OrderSetting', null=True, blank=True, on_delete=models.SET_NULL,
                                      help_text="주문 전략 설정")
    pension_base_diff = models.IntegerField(help_text="계좌 연금 이전 시 원금과 평가금 차액", default=0, null=False)

    objects = AccountDetectionManger()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_fields = {}
        self.set_init_fields()

    def __str__(self):
        return f'{self.account_alias}({self.vendor_code} {self.ACCOUNT_TYPE[self.account_type]})'

    @reversion_diff
    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)
        self.set_init_fields()

    def set_init_fields(self):
        for _field in self._meta.fields:
            self._init_fields[_field.name] = getattr(self, _field.name)

    def get_period_amount(self, from_date: datetime or str = None, to_date: datetime or str = None, use_realtime=True):
        filter_kwargs = {}
        last_inquiry_date = None
        from_date = convert_datetime_kst(dt=from_date, dt_format='%Y-%m-%d')
        to_date = convert_datetime_kst(dt=to_date, dt_format='%Y-%m-%d')

        for _dt, _query_filter in zip([from_date, to_date], ['created_at__gt', 'created_at__lte']):
            if isinstance(_dt, datetime):
                filter_kwargs[_query_filter] = _dt

        queryset = self.amounthistory_set.order_by('created_at')
        if queryset.exists():
            last_inquiry_date = get_datetime_kst(queryset.values_list('created_at', flat=True).last())
            if to_date and last_inquiry_date > to_date:
                use_realtime = False

        today_amount = {}
        if use_realtime:
            realtime_filter_kwargs = {
                'from_date': last_inquiry_date,
                'to_date': to_date
            }
            try:
                today_amount = AmountHistory.get_realtime_period_amount(acct=self, **realtime_filter_kwargs)
                if today_amount:
                    today_amount['input_amt'] -= today_amount['input_usd_amt']
                    today_amount['output_amt'] -= today_amount['output_usd_amt']
            except PreconditionFailed as e:
                logger.warning(f"get_realtime_period_amount: {e}")

        amount_keys = [k for k in AmountHistory.__dict__.keys() if k.endswith('amt')]
        today_delta = pd.Series(today_amount, index=amount_keys).fillna(0)
        df = pd.DataFrame(queryset.filter(**filter_kwargs).values(*amount_keys), columns=amount_keys)
        acc_df = (df.fillna(0).astype(float).sum(axis=0) + today_delta).round(2)
        return acc_df.to_dict()

    def get_amount(self, from_date: datetime or str = None, to_date: datetime or str = None, use_realtime=True):
        filter_kwargs = {}
        from_date = convert_datetime_kst(dt=from_date, dt_format='%Y-%m-%d')
        to_date = convert_datetime_kst(dt=to_date, dt_format='%Y-%m-%d')
        last_inquiry_date = from_date

        for _dt, _query_filter in zip([from_date, to_date], ['trd_date__gte', 'trd_date__lte']):
            if isinstance(_dt, datetime):
                filter_kwargs[_query_filter] = _dt

        # From DB
        queryset = self.trade_set.filter(**filter_kwargs).order_by('trd_date')
        trades = list(queryset.values())

        if queryset.exists():
            last_inquiry_date = convert_datetime_kst(dt=str(queryset.values_list('trd_date').last()[0]), dt_format='%Y-%m-%d') + timedelta(days=1)
            if to_date and last_inquiry_date > to_date:
                use_realtime = False

        if use_realtime:
            realtime_filter_kwargs = {
                'from_date': last_inquiry_date,
                'to_date': to_date
            }
            try:
                # From TR
                trades = trades + self.get_realtime_trades(**realtime_filter_kwargs)
            except PreconditionFailed as e:
                logger.warning(f"get_realtime_period_trades: {e}")

        amount = CheckBaseAmountCalculator(acct=self, trade_df=pd.DataFrame(trades)).calculate()

        return amount

    def get_realtime_trades(self, from_date: datetime, to_date: datetime):
        payload = {}

        if isinstance(from_date, datetime):
            payload['from_date'] = from_date.strftime('%Y%m%d')
        if isinstance(to_date, datetime):
            payload['to_date'] = to_date.strftime('%Y%m%d')

        resp = req.get(f"{settings.TR_BACKEND}/api/v1/kb/accounts/{self.account_number}/trades" ,params=payload)

        if resp:
            return resp.json().get('trades', [])
        else:
            raise PreconditionFailed(f"Can't retrieve account trades")


class Asset(Timestampable, models.Model):
    id = models.BigAutoField(primary_key=True)
    account_alias = models.ForeignKey(Account, on_delete=models.CASCADE, help_text="계좌번호 별칭")
    base = models.IntegerField(null=False, help_text="투자원금(KRW)")
    deposit = models.IntegerField(null=False, help_text="예수금(KRW)")
    balance = models.IntegerField(null=False, help_text="평가금(KRW)")
    prev_deposit = models.IntegerField(null=False, help_text="전일자 예수금(KRW)")
    base_usd = models.FloatField(null=False, help_text="투자원금(USD)")
    deposit_usd = models.FloatField(null=False, help_text="예수금(USD)")
    balance_usd = models.FloatField(null=False, help_text="평가금(USD)")

    class Meta:
        unique_together = (('account_alias', 'created_at'),)

    @property
    def profit_loss(self):
        _eval_amt = self.eval_amt
        if self.base is None or _eval_amt is None:
            return None
        return _eval_amt - self.base

    @property
    def eval_amt(self):
        if self.deposit is None or self.balance is None:
            return None
        return self.balance + self.deposit


class AssetDetail(Timestampable, models.Model):
    id = models.BigAutoField(primary_key=True)
    account_alias = models.ForeignKey(Account, on_delete=models.CASCADE, help_text="계좌번호 별칭")
    code = models.CharField(null=False, max_length=12, help_text="ISIN 코드")
    shares = models.DecimalField(null=False, help_text="좌수", max_digits=30, decimal_places=6)
    buy_price = models.IntegerField(null=False, help_text="매수금(KRW)")
    balance = models.IntegerField(null=False, help_text="평가금(KRW)")
    buy_price_usd = models.FloatField(null=False, help_text="매수금(USD)")
    balance_usd = models.FloatField(null=False, help_text="평가금(USD)")

    class Meta:
        unique_together = (('account_alias', 'code', 'created_at'),)


class Trade(Timestampable, models.Model):
    objects = TradeQuerySet.as_manager()

    id = models.BigAutoField(primary_key=True)
    account_alias = models.ForeignKey(Account, on_delete=models.CASCADE, help_text="계좌번호 별칭")
    trd_date = models.DateField(max_length=8, help_text='거래일자')
    ord_no = models.IntegerField(help_text='거래일련번호')
    quantity = models.DecimalField(blank=True, null=True, max_digits=30, decimal_places=6, help_text='거래수량')
    deposit_amt = models.IntegerField(blank=True, null=True, help_text='예수금잔고')
    commission = models.IntegerField(blank=True, null=True, help_text='국내수수료')
    in_come_tax = models.IntegerField(blank=True, null=True, help_text='소득세')
    currency_name = models.CharField(blank=True, null=True, max_length=40, help_text='통화구분명')
    pre_p_deposit = models.IntegerField(blank=True, null=True, help_text='결제선납입금액')
    ex_deposit = models.FloatField(blank=True, null=True, help_text='외화예수금잔액')
    j_name = models.CharField(blank=True, null=True, max_length=35, help_text='적요명')
    settled_amt = models.IntegerField(blank=True, null=True, help_text='원화정산금액')
    trd_p = models.DecimalField(blank=True, null=True, max_digits=30, decimal_places=6, help_text='결제단가')
    trd_tax = models.DecimalField(blank=True, null=True, max_digits=30, decimal_places=6, help_text='제세금')
    reside_tax = models.IntegerField(help_text='주민세')
    perfor_qty = models.DecimalField(blank=True, null=True, max_digits=30, decimal_places=4, help_text='유가증권변제수량')
    ex_chg_rate = models.FloatField(blank=True, null=True, max_length=11, help_text='환율')
    pre_pay_repay = models.IntegerField(help_text='결제선납입금액변제')
    stock_name = models.CharField(blank=True, null=True, max_length=50, help_text='종목명')
    trd_amt = models.DecimalField(blank=True, null=True, max_digits=30, decimal_places=4, help_text='거래금액')
    agr_tax = models.IntegerField(blank=True, null=True, help_text='농특세')
    unpaid_repay = models.IntegerField(blank=True, null=True, help_text='미수변제금액')
    etc_repay = models.IntegerField(blank=True, null=True, help_text='기타대여금변제금액')
    stock_qtry = models.DecimalField(blank=True, null=True, max_digits=30, decimal_places=6, help_text='유가증권잔고수량')
    for_comm_r = models.FloatField(blank=True, null=True, help_text='국외수수료')
    for_amt_r = models.FloatField(blank=True, null=True, help_text='외화정산금액')
    st_stock_code = models.CharField(blank=True, null=True, max_length=12, help_text='표준종목코드')
    for_amt = models.IntegerField(blank=True, null=True, help_text='외화예수금')
    j_code = models.CharField(blank=True, null=True, max_length=3, help_text='적요유형코드')


    class Meta:
        unique_together = ('account_alias', 'trd_date', 'ord_no')


class Execution(Timestampable, models.Model):
    objects = ExecutionQuerySet.as_manager()

    id = models.BigAutoField(primary_key=True)
    account_alias = models.ForeignKey(Account, on_delete=models.CASCADE, help_text="계좌번호 별칭")
    order_date = models.DateField(help_text='체결일자')
    ord_no = models.IntegerField(help_text="주문번호")
    code_name = models.CharField(help_text="종목명", max_length=40, null=True)
    code = models.CharField(help_text="단축종목코드", max_length=12, null=True)
    trade_sec_name = models.CharField(help_text="거래구분명", max_length=8, null=True)
    order_status = models.CharField(help_text="주문상태명", max_length=8, null=True)
    exec_qty = models.DecimalField(help_text="체결수량", max_digits=30, decimal_places=6)
    exec_price = models.DecimalField(help_text="체결수량", max_digits=15, decimal_places=4)

    ord_qty = models.DecimalField(help_text="주문수량", max_digits=30, decimal_places=6)
    ord_price = models.DecimalField(help_text="주문수량", max_digits=15, decimal_places=4)
    unexec_qty = models.DecimalField(help_text="미체결수량", null=True, max_digits=30, decimal_places=6)
    org_ord_no = models.IntegerField(help_text="원주문번호", null=True)
    mkt_clsf_nm = models.CharField(help_text="시장구분명", max_length=10)
    currency_code = models.CharField(help_text="통화코드", max_length=3, null=True)
    ord_sec_name = models.CharField(help_text="주문구분명", max_length=10, null=True)
    from_time = models.TimeField(help_text="시작시간", null=True)
    to_time = models.TimeField(help_text="종료시간", null=True)
    order_tool_name = models.CharField(help_text="주문매체명", max_length=50)
    order_time = models.TimeField(help_text="주문시간", null=True)
    aplc_excj_rate = models.DecimalField(help_text="적용환율", max_digits=9, decimal_places=4)
    reject_reason = models.CharField(help_text="거부사유", max_length=100, null=True)
    ex_code = models.CharField(help_text="해외거래소구분코드", max_length=3, null=True)
    loan_date = models.CharField(help_text="대출일자", null=True, max_length=8)
    org_price = models.DecimalField(help_text="주문가격", max_digits=15, decimal_places=4)
    exchange_rate = models.DecimalField(help_text="환율", max_digits=9, decimal_places=4)
    frgn_stp_prc = models.DecimalField(help_text="해외중단가격(P4)", max_digits=16, decimal_places=4)
    frgn_brkr_ccd = models.CharField(help_text="해외브로커구분코드", max_length=2, null=True)


    class Meta:
        unique_together = ('account_alias', 'order_date', 'ord_no')


class SumUp(Timestampable, models.Model):
    _AMOUNT_FUNCS = [
        ('INPUT', '원화 입금'), ('OUTPUT', '원화 출금'),
        ('INPUT_USD', '외화 입금'), ('OUTPUT_USD', '외화 출금'),
        ('IMPORT', '입고'), ('EXPORT', '출고'),
        ('DIVIDEND_INPUT', '배당금 입금'), ('DIVIDEND_OUTPUT', '배당금 출금'),
        ('OVERSEA_TAX', '해외 수수료'), ('OVERSEA_TAX_REFUND', '해외 수수료 반환'),
    ]
    AMOUNT_FUNC_TYPES = Choices(*_AMOUNT_FUNCS)

    _TRD_TYPE = [*_AMOUNT_FUNCS,
                 ('BID', '매수'), ('ASK', '매도'), ('SETTLEMENT_IN', '정산(입금)'), ('SETTLEMENT_OUT', '정산(출금)'),
                 ('EXCHANGE', '환전'), ('INTEREST_DEPOSIT', '이자 입금')]

    TRADE_TYPES = Choices(*_TRD_TYPE)

    j_name = models.CharField(blank=True, null=True, max_length=35, help_text='적요명')
    j_code = models.CharField(blank=True, null=True, max_length=3, help_text='적요유형코드')
    amount_func_type = models.CharField(max_length=30, blank=True, null=True, choices=AMOUNT_FUNC_TYPES)
    trade_type = models.CharField(max_length=30, blank=True, null=True, choices=TRADE_TYPES)
    managed = models.BooleanField(default=False, help_text="관리여부")
    description = models.CharField(max_length=100, blank=True, null=True, help_text="설명")

    class Meta:
        unique_together = ('j_name', 'j_code')

    @staticmethod
    def get_amount_func_types(queryset):
        amount_func_types = defaultdict(list)
        for _j_name, _amount_func_type in queryset.values_list('j_name', 'amount_func_type'):
            if _amount_func_type:
                amount_func_types[_amount_func_type].append(_j_name)
        return amount_func_types

    @staticmethod
    def get_trade_types(queryset):
        trade_types = defaultdict(list)
        for _j_name, _trade_type in queryset.values_list('j_name', 'trade_type'):
            if _trade_type:
                trade_types[_trade_type].append(_j_name)
        return trade_types


class SettlementManager(models.Manager):
    FFILL_COLUMNS = ['deposit', 'for_deposit']
    FILL_ZERO_COLUMNS = ['input_amt', 'dividend', 'dividend_input_amt', 'output_amt', 'settled_for_amt', 'commission',
                         'in_come_tax', 'for_trd_tax', 'for_commission', 'reside_tax']
    ROUND_COLUMNS = ['base', 'settled_for_amt', 'for_commission', 'for_trd_tax']
    TRADE_TYPE_MAPS = SumUp.get_trade_types(SumUp.objects.all())
    DECIMAL_POINTS = 2

    def settle(self, account_alias_id, to_date=None, use_registered=True):
        if use_registered:
            registered_settle_df = self.get_settle_df(account_alias_id=account_alias_id, to_date=to_date)
        else:
            registered_settle_df = pd.DataFrame()

        settle_df = self._settle_df(account_alias_id=account_alias_id,
                                    registered_settle_df=registered_settle_df, to_date=to_date)
        unregistered_settle_df = settle_df.loc[set(settle_df.index) - set(registered_settle_df.index)]

        if not unregistered_settle_df.empty:
            _updated_at = timezone.now()
            unregistered_settle_df.index = unregistered_settle_df.index.tz_localize(settings.TIME_ZONE)
            _instances = [Settlement(**row, created_at=i, updated_at=_updated_at) for i, row in
                          unregistered_settle_df.iterrows()]
        else:
            _instances = []
        return _instances

    def _settle_df(self, account_alias_id, registered_settle_df, to_date):
        _last_settle_date = None
        if not registered_settle_df.empty:
            _last_settle_date = registered_settle_df.index[-1]

        trade_df = self.get_trade_df(account_alias_id=account_alias_id,
                                     last_settle_date=_last_settle_date, to_date=to_date)
        settlement_df = trade_df.groupby(by='base_date').apply(self._settle_daily, self.TRADE_TYPE_MAPS)

        if settlement_df.empty:
            return settlement_df

        settlement_df.loc[registered_settle_df.index] = registered_settle_df
        settlement_df['account_alias_id'] = account_alias_id

        if not registered_settle_df.empty:
            calculated_settle_df = settlement_df.loc[set(settlement_df.index) - set(registered_settle_df.index)]
            calculated_settle_df.loc[registered_settle_df.index[-1]] = registered_settle_df.iloc[-1]
        else:
            calculated_settle_df = settlement_df

        calculated_settle_df = calculated_settle_df.sort_index()
        calculated_settle_df[self.FFILL_COLUMNS] = calculated_settle_df[self.FFILL_COLUMNS].ffill().fillna(0)
        calculated_settle_df[self.FILL_ZERO_COLUMNS] = calculated_settle_df[self.FILL_ZERO_COLUMNS].fillna(0)
        calculated_settle_df['base'] = calculated_settle_df['base'].fillna(0).cumsum()
        calculated_settle_df[self.ROUND_COLUMNS] = calculated_settle_df[self.ROUND_COLUMNS].round(self.DECIMAL_POINTS)
        settlement_df.loc[calculated_settle_df.index] = calculated_settle_df
        return settlement_df.fillna(0)

    @staticmethod
    def _settle_daily(daily_trade_df: pd.DataFrame, trade_type_maps):
        columns = [
            'account_alias_id',
            'base', 'deposit', 'for_deposit', 'dividend', 'dividend_input_amt',
            'settled_for_amt',
            'commission', 'in_come_tax', 'reside_tax', 'for_trd_tax',
            'for_commission']
        _row = {k: np.nan for k in columns}

        base_amt_calculator = BaseAmountCalculator(daily_trade_df)
        _base_amt = base_amt_calculator.calculate()

        for k in ['base', 'input_amt', 'output_amt', 'dividend', 'dividend_input_amt', 'stock_import_amt',
                  'stock_export_amt']:
            _row[k] = _base_amt[k]

        krw_cash_io_sumup = []
        for k in ['INPUT', 'OUTPUT', 'SETTLEMENT_IN', 'SETTLEMENT_OUT']:
            krw_cash_io_sumup += trade_type_maps[k]

        for_cash_io_sumup = []
        for k in ['INPUT_USD', 'OUTPUT_USD', 'SETTLEMENT_IN', 'SETTLEMENT_OUT', 'EXCHANGE', 'DIVIDEND_INPUT',
                  'OVERSEA_TAX']:
            for_cash_io_sumup += trade_type_maps[k]

        settlement_cash = daily_trade_df[daily_trade_df.j_name.isin(krw_cash_io_sumup)]
        settlement_for_cash = daily_trade_df[daily_trade_df.j_name.isin(for_cash_io_sumup)]
        _settled_bid_basis = daily_trade_df[daily_trade_df.j_name.isin(['매수'])]
        _settled_ask_basis = daily_trade_df[daily_trade_df.j_name.isin(['매도'])]

        daily_trade_aggr = daily_trade_df[['commission', 'in_come_tax']].sum(axis=0)
        settled_bid_aggr = _settled_bid_basis[['trd_tax', 'trd_amt', 'for_amt_r', 'for_comm_r', 'reside_tax']].astype(
            float).sum(axis=0)
        settled_ask_aggr = _settled_ask_basis[['trd_tax', 'trd_amt', 'for_amt_r', 'for_comm_r', 'reside_tax']].astype(
            float).sum(axis=0)

        if not settlement_cash.empty:
            _last_settlement_cash = settlement_cash.sort_values(by='ord_no', ascending=False)
            _row['deposit'] = _last_settlement_cash.deposit_amt.values[0]

        if not settlement_for_cash.empty:
            _last_settlement_for_cash = settlement_for_cash.sort_values(by='ord_no', ascending=False)
            _row['for_deposit'] = _last_settlement_for_cash.ex_deposit.values[0]

        settled_for_amt = 0.0
        if not _settled_bid_basis.empty:
            settled_for_amt += settled_bid_aggr['trd_amt']

        if not _settled_ask_basis.empty:
            settled_for_amt -= settled_ask_aggr['trd_amt']

        _row['settled_for_amt'] = settled_for_amt
        _row['for_commission'] = settled_bid_aggr.for_comm_r + settled_ask_aggr.for_comm_r
        _row['for_trd_tax'] = settled_bid_aggr.trd_tax + settled_ask_aggr.trd_tax
        _row['reside_tax'] = settled_bid_aggr.reside_tax + settled_ask_aggr.reside_tax
        _row['commission'] = daily_trade_aggr['commission']
        _row['in_come_tax'] = daily_trade_aggr['in_come_tax']
        _row['import_amt'] = _row.pop('stock_import_amt', 0)
        _row['export_amt'] = _row.pop('stock_export_amt', 0)
        return pd.Series(_row)

    @staticmethod
    def get_settle_df(account_alias_id, to_date):
        filter_kwargs = {
        }

        if to_date:
            filter_kwargs['created_at__date__lte'] = to_date

        _settle_df = pd.DataFrame(Settlement.objects.filter(
            account_alias_id=account_alias_id, **filter_kwargs).values())

        if not _settle_df.empty:
            _settle_df = _settle_df.set_index('created_at')
            _settle_df.index = pd.to_datetime(_settle_df.index.tz_convert(pytz.timezone('Asia/Seoul')).date)
        _settle_df.index.name = 'base_date'
        return _settle_df

    @staticmethod
    def get_trade_df(account_alias_id, last_settle_date=None, to_date=None):
        filter_kwargs = {
        }

        if last_settle_date:
            filter_kwargs['trd_date__gt'] = last_settle_date
        if to_date:
            filter_kwargs['trd_date__lte'] = to_date

        queryset = Trade.objects.filter(account_alias_id=account_alias_id, **filter_kwargs)

        trade_df = pd.DataFrame(queryset.values())
        if not trade_df.empty:
            trade_df = trade_df.set_index('trd_date')
            trade_df.index = pd.to_datetime(list(trade_df.index))
        trade_df.index.name = 'base_date'
        return trade_df

    @staticmethod
    def get_execution_df(account_alias_id, last_settle_date=None, to_date=None):
        filter_kwargs = {
        }

        if last_settle_date:
            filter_kwargs['order_date__gt'] = last_settle_date
        if to_date:
            filter_kwargs['order_date__lte'] = to_date

        queryset = Execution.objects.filter(account_alias_id=account_alias_id, **filter_kwargs)

        exec_df = pd.DataFrame(queryset.values())
        if not exec_df.empty:
            exec_df = exec_df.set_index('order_date')
            exec_df.index = pd.to_datetime(list(exec_df.index))
        exec_df.index.name = 'base_date'
        return exec_df


class Holding(Timestampable, models.Model):
    objects = HoldingQuerySet.as_manager()

    account_alias = models.ForeignKey(Account, on_delete=models.CASCADE, help_text="계좌번호 별칭")
    code = models.CharField(null=False, max_length=12, help_text="ISIN 코드")
    shares = models.DecimalField(null=False, help_text="보유좌수", max_digits=30, decimal_places=6)

    class Meta:
        unique_together = ('account_alias', 'created_at', 'code')

    def __str__(self):
        return f"Holding({self.code}, {self.shares}, {self.created_at.date()})"


class AmountHistory(Timestampable, models.Model):
    account_alias = models.ForeignKey(Account, on_delete=models.CASCADE, help_text="계좌번호 별칭")
    input_amt = models.BigIntegerField(default=0, help_text="입금액")
    output_amt = models.BigIntegerField(default=0, help_text="출금액")
    input_usd_amt = models.BigIntegerField(default=0, help_text="외화입금액(원화환산)")
    output_usd_amt = models.BigIntegerField(default=0, help_text="외화출금액(원화환산)")
    import_amt = models.DecimalField(default=0, help_text="입고계", max_digits=30, decimal_places=6)
    export_amt = models.DecimalField(default=0, help_text="출고계", max_digits=30, decimal_places=6)
    dividend_input_amt = models.DecimalField(default=0, max_digits=15, decimal_places=4, help_text="배당금(세전)")
    dividend_output_amt = models.DecimalField(default=0, max_digits=15, decimal_places=4, help_text="배당금 출금(세전)")
    oversea_tax_amt = models.DecimalField(default=0, max_digits=15, decimal_places=4, help_text="해외수수료")
    oversea_tax_refund_amt = models.DecimalField(default=0, max_digits=15, decimal_places=4, help_text="해외수수료 반환금")

    stock_transfer_amt = models.DecimalField(default=0, decimal_places=6, max_digits=30, help_text="입출고 총계")
    stock_import_amt = models.DecimalField(default=0, decimal_places=6, max_digits=30, help_text="입고 총계")
    stock_export_amt = models.DecimalField(default=0, decimal_places=6, max_digits=30, help_text="출고 총계")

    class Meta:
        unique_together = (('account_alias', 'created_at'),)

    @staticmethod
    def get_realtime_period_amount(acct: Account, from_date: datetime, to_date: datetime):
        payload = {}
        if isinstance(from_date, datetime):
            payload['from_date'] = from_date.strftime('%Y%m%d')
        if isinstance(to_date, datetime):
            payload['to_date'] = to_date.strftime('%Y%m%d')

        payload = {
            "ci_valu": "m2OAplW5ED4R9TNHHYwtSh/iechcSKyqRfirZfg61wKNwDuLyzzNib2/+ghO7walecN5g1M6fCCTsLj68WDaGQ==",
            "acct_alias": acct.account_alias,
            "start_date": "20220101",
            "end_date": "20230106"
        }
        TR_MAP = {
            "kb": req.get(f"{settings.TR_BACKEND}/api/v1/kb/accounts/{acct.account_number}/trades", params=payload),
            "hanaw": req.post(f"{settings.HANAW_BACKEND}/api/v1/hanaw/account/trading", data=payload)
        }

        resp = TR_MAP[acct.vendor_code]

        if acct.vendor_code == 'hanaw':
            resp = resp.json().get('dataBody', [])
            # resp = resp.get('records', [])

        if resp:
            trades = resp.json().get('trades', 'records')
            if trades:
                amount_calculator = BaseAmountCalculator(acct=acct, trade_df=pd.DataFrame(trades))
                return amount_calculator.calculate()
        else:
            raise PreconditionFailed(f"Can't retrieve account trades")
        return {}


class Settlement(Timestampable, models.Model):
    account_alias = models.ForeignKey(Account, on_delete=models.CASCADE, help_text="계좌번호 별칭")

    base = models.BigIntegerField(default=0, help_text="투자원금")
    deposit = models.BigIntegerField(default=0, help_text="원화 예수금 잔고(KRW)")
    for_deposit = models.DecimalField(default=0, help_text="외화 예수금 잔고(USD)", max_digits=15, decimal_places=4)
    input_amt = models.BigIntegerField(default=0, help_text="입금액")
    output_amt = models.BigIntegerField(default=0, help_text="출금액")
    import_amt = models.DecimalField(default=0, help_text="입고계", max_digits=30, decimal_places=6)
    export_amt = models.DecimalField(default=0, help_text="출고계", max_digits=30, decimal_places=6)

    dividend = models.DecimalField(null=True, max_digits=15, decimal_places=4, help_text="배당금(세후)")
    dividend_input_amt = models.DecimalField(null=True, max_digits=15, decimal_places=4, help_text="배당금(세전)")

    commission = models.DecimalField(help_text="국내 수수료", max_digits=15, decimal_places=4)
    in_come_tax = models.DecimalField(help_text='국내 소득세', max_digits=15, decimal_places=4)
    reside_tax = models.DecimalField(help_text="주민세", max_digits=15, decimal_places=4)

    settled_for_amt = models.DecimalField(null=True, help_text="당일 결제 대금(USD, 세전)", max_digits=15, decimal_places=4)
    settled_for_bid_amt = models.DecimalField(null=True, help_text="당일 매수 결제 대금(USD, 세전)", max_digits=15,
                                              decimal_places=4)
    settled_for_ask_amt = models.DecimalField(null=True, help_text="당일 매도 결제 대금(USD, 세전)", max_digits=15,
                                              decimal_places=4)

    settled_amt = models.BigIntegerField(null=True, help_text="당일 결제 대금(KRW, 세전)")
    settled_bid_amt = models.BigIntegerField(null=True, help_text="당일 매수 결제 대금(KRW, 세전)")
    settled_ask_amt = models.BigIntegerField(null=True, help_text="당일 매도 결제 대금(KRW, 세전)")

    for_trd_tax = models.DecimalField(help_text="미결제 해외 거래 세금(USD)", max_digits=15, decimal_places=4)
    for_commission = models.DecimalField(help_text='미결제 국외수수료(USD)', max_digits=15, decimal_places=4)

    objects = SettlementManager()


class DailyBalance(Timestampable, models.Model):
    account_alias = models.ForeignKey(Account, on_delete=models.CASCADE, help_text="계좌번호 별칭")
    base = models.BigIntegerField(default=0, help_text="투자원금")
    deposit = models.BigIntegerField(default=0, help_text="투자원금")
    for_deposit = models.DecimalField(default=0, help_text="외화 예수금 잔고(USD)", max_digits=15, decimal_places=4)
    unsettled_for_amt = models.DecimalField(default=0, help_text="외화 예수금 잔고(USD)", max_digits=15, decimal_places=4)
    balance_usd = models.DecimalField(default=0, help_text="외화 예수금 잔고(USD)", max_digits=15, decimal_places=4)
    balance = models.BigIntegerField(default=0, help_text="투자원금")
    liquidity = models.BigIntegerField(default=0, help_text="투자원금")
    exchange_rate = models.DecimalField(help_text="환율", max_digits=9, decimal_places=4)
    profit_loss = models.BigIntegerField(default=0, help_text="평가손익")
