import asyncio
import datetime
import logging
from decimal import Decimal
from itertools import islice
from typing import List

import aiohttp
import pandas as pd
import pytz
from django.conf import settings
from django.db.models import Max
from django.utils import timezone
from rest_framework import serializers, exceptions
from rest_framework.generics import get_object_or_404

from api.bases.accounts.calcuator import BaseAmountCalculator
from api.bases.accounts.models import (
    Account, Asset, AssetDetail, AmountHistory,
    Trade, Execution, SumUp,
    Settlement, Holding,
    DailyBalance
)
from common.exceptions import PreconditionFailed, DuplicateAccess
from common.utils import get_local_today, KST_TZ, convert_datetime_kst

logger = logging.getLogger('django.server')


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = '__all__'
        read_only_fields = ('status', 'pension_base_diff',)
        extra_kwargs = {
            'strategy_code': {'allow_null': True}
        }

    def to_internal_value(self, data):
        internal_value = super(AccountSerializer, self).to_internal_value(data)
        internal_value['strategy_code'] = internal_value.get('strategy_code', 0) or 0
        return internal_value

    def is_valid(self, raise_exception=False):
        if super().is_valid(raise_exception=raise_exception):
            vendor_code = self.validated_data.get('vendor_code')
            account_number = self.validated_data.get('account_number')
            for item in Account.objects.filter(
                    vendor_code=vendor_code).exclude(status=Account.STATUS.canceled).values(
                'account_number').iterator():
                if item.get('account_number') == account_number:
                    raise exceptions.ValidationError({'account_number': 'this account number is already exists.'})
            return True
        return False


class AccountUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = '__all__'
        read_only_fields = (
            'account_alias',
            'vendor_code',
            'account_number',
            'account_type',
            'created_at',
            'updated_at',
            'deleted_at',
            'pension_base_diff'
        )


class AccountDumpInputSerializer(serializers.Serializer):
    class AccountDumpDataSerializer(serializers.ModelSerializer):
        class Meta:
            model = Account
            fields = ['account_alias', 'account']

        account = serializers.CharField(source='account_number')

    account_list = AccountDumpDataSerializer(many=True)
    date = serializers.DateTimeField(format='%Y%m%d', help_text="기준일")

    def to_representation(self, instance):
        representation = super().to_representation(instance=instance)
        representation['date'] = representation['date']
        return representation


class AccountPensionDumpInputSerializer(serializers.Serializer):
    class AccountPensionDumpDataSerializer(serializers.ModelSerializer):
        class Meta:
            model = Account
            fields = ['account_alias', 'account', 'pension_base_diff']

        account = serializers.CharField(source='account_number')

    account_list = AccountPensionDumpDataSerializer(many=True)
    date = serializers.DateTimeField(format='%Y%m%d', help_text="기준일")

    def to_representation(self, instance):
        representation = super().to_representation(instance=instance)
        representation['date'] = representation['date']
        return representation

class AssetDumpDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ('base', 'balance', 'deposit', 'prev_deposit',
                  'base_usd', 'balance_usd', 'deposit_usd')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        for k, v in representation.items():
            if k.endswith('_usd'):
                representation[k] = round(v, 3)
        return representation


class AccountAssetDumpDataSerializer(serializers.Serializer):
    account = serializers.CharField(help_text="실계좌번호")
    account_alias = serializers.CharField(help_text="계좌별칭")
    asset = AssetDumpDataSerializer(help_text="자산")


class AccountAssetDumpSerializer(serializers.Serializer):
    __tr_dump_api_path = '/api/v1/kb/accounts/batch/asset/days'
    __default_task_size = 1

    def to_internal_value(self, data):
        data['account_list'] = data['account_list'][:30]
        task_size = int(self.context.get('task_size', self.__default_task_size))
        if task_size < 1:
            raise serializers.ValidationError("Task size must be larger than 0")

        subset_size = int(len(data['account_list']) / task_size)
        return asyncio.run(self.divide_conquer(data, subset_size=subset_size))

    async def divide_conquer(self, data, subset_size: int):
        account_subset = list(self.divide_iter(data['account_list'], subset_size))
        request_tasks = [
            asyncio.create_task(self.async_request_tr_dump(accounts=_subset, date=data['date'], idx=idx))
            for idx, _subset in enumerate(account_subset)
        ]
        async_responses = await asyncio.gather(*request_tasks)
        response = {"result": sum(async_responses, [])}
        return response

    def divide_iter(self, accounts: List[str], size) -> List[List[str]]:
        it = iter(accounts)
        return iter(lambda: tuple(islice(it, size)), ())

    async def async_request_tr_dump(self, accounts: List[str], date, idx):
        logger.debug(f"Start {idx}th subset {len(accounts)}")
        target_url = f"{settings.TR_BACKEND}/{self.__tr_dump_api_path}?include_base=false"
        payload = {'account_list': accounts, 'date': date}

        async with aiohttp.ClientSession() as session:
            async with session.post(url=target_url, json=payload) as response:
                resp = await response.json()
                result = resp.get('result', [])
                logger.debug(f"Done {idx}th subset {len(accounts)}, result_size: {len(result)}")
                return result

    result = AccountAssetDumpDataSerializer(many=True)

    @staticmethod
    def get_prev_deposit(acct: Account, base_date: datetime.datetime):
        try:
            target_amount_history = acct.amounthistory_set.get(created_at=convert_datetime_kst(base_date))
            prev_deposit = target_amount_history.input_amt - target_amount_history.output_amt
        except AmountHistory.DoesNotExist:
            prev_deposit = 0
        return prev_deposit

    def iter_asset_representation(self, queryset, results, to_date):
        for acct in results:
            try:
                acct_instance = queryset.get(account_alias=acct['account_alias'])
                serializer = AccAmountHistorySerializer(data=acct_instance.get_period_amount(to_date=to_date))
                serializer.is_valid(raise_exception=True)
                acct_amt = serializer.data
                acct['asset']['base'] = acct_amt.get('base_amt')
                base_usd = 0
                if acct['asset']['balance'] > 0:
                    exchange_rate = acct['asset']['balance'] / acct['asset']['balance_usd']
                    if exchange_rate > 0:
                        base_usd = float(acct['asset']['base']) / float(exchange_rate)
                acct['asset']['base_usd'] = round(base_usd, 3)
                acct['asset']['prev_deposit'] = self.get_prev_deposit(acct=acct_instance,
                                                                      base_date=to_date - datetime.timedelta(days=1))
                yield AccountAssetDumpDataSerializer(acct).data

            except Exception as e:
                logger.warning(f"{e}")

    def to_representation(self, instance):
        alias_set = [i['account_alias'] for i in instance['result']]
        queryset = Account.objects.filter(account_alias__in=alias_set)
        to_date = convert_datetime_kst(dt=self.initial_data['date'], dt_format='%Y%m%d')
        result_iter = self.iter_asset_representation(queryset=queryset, results=instance['result'], to_date=to_date)
        return {"result": list(result_iter)}


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = '__all__'


class AssetDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetDetail
        fields = '__all__'


class AccountTradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trade
        fields = '__all__'


class AccountExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Execution
        fields = '__all__'


class AmountHistorySerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(help_text='생성일')

    class Meta:
        model = AmountHistory
        fields = '__all__'


class AmountHistoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmountHistory
        fields = ('account_alias',)

    def save(self):
        acct_instance = self.validated_data['account_alias']
        amount_history_queryset = acct_instance.amounthistory_set.order_by('-created_at')
        filter_kwargs = {
            'trd_date__lt': get_local_today()
        }

        if amount_history_queryset.exists():
            last_amount_history = amount_history_queryset.first()
            filter_kwargs['trd_date__gte'] = last_amount_history.created_at.astimezone(pytz.timezone('Asia/Seoul'))

        amount_history = self.get_amount_history(acct=acct_instance, filter_kwargs=filter_kwargs)

        if amount_history:
            bulk_serializer = AmountHistorySerializer(data=amount_history, many=True)
            bulk_serializer.is_valid(raise_exception=True)
            bulk_serializer.save()

    @classmethod
    def get_amount_history(cls, acct: Account, filter_kwargs=None):
        if not filter_kwargs:
            filter_kwargs = dict()

        trade_df = pd.DataFrame(acct.trade_set.filter(**filter_kwargs).values())
        if trade_df.empty:
            return []

        amount_calculator = BaseAmountCalculator(trade_df=trade_df, acct=acct)
        classified = amount_calculator.classify()
        pivoted = classified.dropna().reset_index().groupby(['trd_date', 'category']).sum().reset_index().pivot(
            columns='category', index='trd_date', values='amt')
        if pivoted.empty:
            return []
        resampled = pivoted.resample('D').first().fillna(0)
        resampled = resampled.rename(columns={c: f"{c.lower()}_amt" for c in resampled.columns}).round(3)
        resampled.index = resampled.index.shift(1)
        resampled.index.name = 'base_date'
        return [{"created_at": i, 'account_alias': acct.pk, **row.to_dict()} for i, row in resampled.iterrows()]


class AmountHistoryUpdateInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmountHistory
        fields = ()


class AmountHistoryUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmountHistory
        fields = (
            'input_amt', 'output_amt',
            'import_amt', 'export_amt',
            'input_usd_amt', 'output_usd_amt',
            'dividend_input_amt', 'dividend_output_amt',
            'oversea_tax_amt', 'oversea_tax_refund_amt'
        )

    @classmethod
    def get_diffs(cls, acct: Account, queryset):
        compare_keys = list(AmountHistoryUpdateSerializer.Meta.fields)
        resettled_df = pd.DataFrame(AmountHistoryCreateSerializer.get_amount_history(acct=acct))

        if not resettled_df.empty:
            resettled_df.set_index('created_at', inplace=True)
            resettled_df.index = cls.get_kst_timestamp(timestamps=pd.to_datetime(resettled_df.index))

            for k in compare_keys:
                if k not in resettled_df.columns:
                    resettled_df[k] = 0

        registered_df = pd.DataFrame(queryset.values())
        if not registered_df.empty:
            registered_df = registered_df.set_index('created_at')
            registered_df.index = cls.get_kst_timestamp(timestamps=pd.to_datetime(registered_df.index))

        resettled_df = resettled_df[resettled_df.index.isin(registered_df.index)]
        diffs = resettled_df[
            (resettled_df[compare_keys].astype(float) != registered_df[compare_keys].astype(float)).any(axis=1)]
        return diffs

    @staticmethod
    def get_kst_timestamp(timestamps: pd.DatetimeIndex):
        if timestamps.tzinfo is None:
            return timestamps.tz_localize(KST_TZ)
        else:
            return timestamps.tz_convert(KST_TZ)


class AccAmountHistorySerializer(serializers.ModelSerializer):
    base_amt = serializers.SerializerMethodField(help_text="입출금 원금")
    input_amt = serializers.IntegerField(default=0, help_text="입금액")
    output_amt = serializers.IntegerField(default=0, help_text="출금액")
    input_usd_amt = serializers.IntegerField(default=0, help_text="외화 입금액")
    output_usd_amt = serializers.IntegerField(default=0, help_text="외화 출금액")
    import_amt = serializers.IntegerField(default=0, help_text="입고액")
    export_amt = serializers.IntegerField(default=0, help_text="출고액")
    transfer_amt = serializers.SerializerMethodField(help_text="입출고액")
    dividend_amt = serializers.SerializerMethodField(help_text="배당금(세후)")
    pretax_dividend_amt = serializers.SerializerMethodField(help_text="배당금(세전)")
    dividend_tax_amt = serializers.SerializerMethodField(help_text="배당금 원천세")
    dividend_input_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="배당입금액(세전)")
    dividend_output_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="배당출금액(세전)")
    oversea_tax_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="배당금 원천세 출금액")
    oversea_tax_refund_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15,
                                                      help_text="배당금 원천세 반환금")

    stock_transfer_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="입출고 총계")
    stock_import_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="입고 총계")
    stock_export_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="출고 총계")

    def get_base_amt(self, attrs) -> Decimal:
        acc_input_amt, acc_output_amt = 0, 0
        for k in ['input_amt', 'import_amt', 'input_usd_amt']:
            acc_input_amt += attrs.get(k, 0)

        for k in ['output_amt', 'export_amt', 'output_usd_amt']:
            acc_output_amt += attrs.get(k, 0)
        return Decimal(acc_input_amt - acc_output_amt)

    def get_pretax_dividend_amt(self, attrs):
        pretax_dividend = attrs.get('dividend_input_amt', 0) - attrs.get('dividend_output_amt', 0)
        return Decimal(round(pretax_dividend, 2))

    def get_dividend_tax_amt(self, attrs):
        return Decimal(round(attrs.get('oversea_tax_amt', 0) - attrs.get('oversea_tax_refund_amt', 0), 2))

    def get_dividend_amt(self, attrs) -> Decimal:
        pretax_dividend = self.get_pretax_dividend_amt(attrs)
        tax = self.get_dividend_tax_amt(attrs)
        return Decimal(round(pretax_dividend - tax, 2))

    def get_transfer_amt(self, attrs) -> int:
        return attrs.get('import_amt', 0) - attrs.get('export_amt', 0)

    def to_internal_value(self, data):
        data['import_amt'] = data.get('import_amt', 0) + data.get('stock_import_amt', 0)
        data['export_amt'] = data.get('export_amt', 0) + data.get('stock_export_amt', 0)
        return data

    def to_representation(self, instance):
        instance = super().to_representation(instance)
        return instance

    class Meta:
        model = AmountHistory
        fields = (
            'base_amt',
            'input_amt', 'output_amt', 'input_usd_amt', 'output_usd_amt',
            'import_amt', 'export_amt', 'transfer_amt',
            'dividend_amt', 'dividend_input_amt', 'dividend_output_amt', 'oversea_tax_amt', 'oversea_tax_refund_amt',
            'pretax_dividend_amt', 'dividend_tax_amt', 'stock_transfer_amt', 'stock_import_amt', 'stock_export_amt'
        )


class AmountHistoryQueueCreateSerializer(serializers.Serializer):
    account_alias_whitelist = serializers.ListField(child=serializers.CharField(max_length=128, help_text="계좌 대체번호"),
                                                    default=[])
    j_names = serializers.ListField(child=serializers.CharField(max_length=35, help_text="적요명"))


class TradeAmountSerializer(serializers.Serializer):
    class PeriodTradeAmountSerializer(serializers.Serializer):
        input_amt = serializers.IntegerField(help_text="기간 입금 총계")
        output_amt = serializers.IntegerField(help_text="기간 입금 총계")
        stock_import_amt = serializers.FloatField(help_text="기간 주식 입고 총계")
        stock_export_amt = serializers.FloatField(help_text="기간 주식 출고 총계")
        stock_transfer_amt = serializers.FloatField(help_text="기간 주식 입출고 총계")
        base_changed = serializers.IntegerField(help_text="기간 원금 변화")

        output_usd_amt = serializers.FloatField(help_text="기간 입금 총계(USD")
        dividend_input_amt = serializers.FloatField(help_text="기간 세전 배당금 입금 총계(USD)")
        dividend_output_amt = serializers.FloatField(help_text="기간 세전 배당금 출금 총계(USD)")
        oversea_tax_amt = serializers.FloatField(help_text="기간 해외 원천세 총계(USD)")
        oversea_tax_refund_amt = serializers.FloatField(help_text="기간 해외 원천세 반 총계(USD)")
        dividend = serializers.FloatField(help_text="기간 세후 배당금 총계(USD)")

    input_amt = serializers.IntegerField(help_text="누적 입금 총계", source='cum.input_amt')
    output_amt = serializers.IntegerField(help_text="누적 입금 총계", source='cum.output_amt')
    stock_import_amt = serializers.FloatField(help_text="누적 주식 입고 총계", source="cum.stock_import_amt")
    stock_export_amt = serializers.FloatField(help_text="누적 주식 출고 총계", source="cum.stock_export_amt")
    stock_transfer_amt = serializers.FloatField(help_text="누적 주식 입출고 총계", source="cum.stock_transfer_amt")
    base_changed = serializers.IntegerField(help_text="누적 원금 변화", source="cum.base_changed")

    output_usd_amt = serializers.FloatField(help_text="누적 입금 총계(USD)", source='cum.output_usd_amt')
    dividend_input_amt = serializers.FloatField(help_text="누적 세전 배당금 총계(USD)", source='cum.dividend_input_amt')
    dividend_output_amt = serializers.FloatField(help_text="기간 세전 배당금 출금 총계(USD)", source='cum.dividend_output_amt')
    oversea_tax_amt = serializers.FloatField(help_text="누적 해외 원천세 총계(USD)", source='cum.oversea_tax_amt')
    oversea_tax_amt_refund = serializers.FloatField(help_text="누적 해외 원천세 총계(USD)", source='cum.oversea_tax_refund_amt')
    dividend = serializers.FloatField(help_text="누적 세후 배당금 총계(USD)", source='cum.dividend')
    period = PeriodTradeAmountSerializer()


class SumUpSerializer(serializers.ModelSerializer):
    class Meta:
        model = SumUp
        fields = '__all__'


class SumUpUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SumUp
        fields = ('amount_func_type', 'trade_type', 'managed', 'description')


class SettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settlement
        fields = '__all__'


class SettlementCreateSerializer(serializers.Serializer):
    account_alias = serializers.CharField(help_text="계좌대체번호")
    to_date = serializers.DateField(required=False)

    def validate_to_date(self, value):
        if value > datetime.datetime.now().date():
            raise serializers.ValidationError("to_date must be before today")
        return value


class SettlementUpdateSerializer(serializers.Serializer):
    to_date = serializers.DateField(required=False)

    def validate_to_date(self, value):
        if value > datetime.datetime.now().date():
            raise serializers.ValidationError("to_date must be before today")
        return value


class HoldingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Holding
        fields = '__all__'


def get_j_name_map():
    j_name_map = SumUp.get_trade_types(SumUp.objects.filter(trade_type__in=['BID', 'ASK', 'IMPORT', 'EXPORT']))
    return j_name_map


class HoldingCreateSerializer(serializers.ModelSerializer):
    account_alias = serializers.CharField(help_text="계좌대체번호")
    to_date = serializers.DateField(default=timezone.now, format='%Y-%m-%d')
    j_name_map = serializers.DictField(default=get_j_name_map)

    class Meta:
        model = Account
        fields = ('account_alias', 'to_date', 'j_name_map')

    def create(self, validated_data):
        acct = get_object_or_404(Account.objects.filter(account_alias=self.validated_data['account_alias']))
        holding_qty_df = self.calc_qty(acct=acct, j_name_map=self.validated_data['j_name_map'])
        instances = sum([
            [
                Holding(account_alias_id=validated_data['account_alias'], code=code, shares=shares,
                        created_at=i.to_pydatetime())
                for code, shares in row.iteritems() if shares > 0
            ]
            for i, row in holding_qty_df.iterrows()], [])
        Holding.objects.bulk_create(instances)
        return instances

    def validate_to_date(self, to_date):
        if to_date > timezone.now().date():
            raise serializers.ValidationError("to_date must be equal or smaller than timezone.now()")
        return to_date

    def calc_qty(self, acct: Account, j_name_map: dict):
        last_registered, last_registered_idx = pd.DataFrame(), None

        to_date = self.validated_data['to_date']
        execution_set_filter_kwargs = {
            'order_date__lte': to_date
        }
        trade_set_filter_kwargs = {
            'trd_date__lte': to_date,
            'j_name__in': [*j_name_map['IMPORT'], *j_name_map['EXPORT']]
        }

        start_candi, end_candi = [], []

        if acct.holding_set.exists():
            last_registered = \
                acct.holding_set.filter(**acct.holding_set.aggregate(created_at=Max('created_at'))).to_df()
            last_registered_idx = last_registered.index[-1]

            last_checked_date = last_registered_idx.to_pydatetime().date()
            execution_set_filter_kwargs['order_date__gte'] = last_checked_date
            trade_set_filter_kwargs['trd_date__gte'] = last_checked_date
            start_candi.append(last_checked_date)

        exec_qty_df = acct.execution_set.filter(**execution_set_filter_kwargs).calc_exec_qty()
        transfer_qty_df = acct.trade_set.filter(**trade_set_filter_kwargs).calc_settle_qty()
        exec_qty_df.index = pd.to_datetime(exec_qty_df.index).shift(1, 'D')
        transfer_qty_df.index = pd.to_datetime(transfer_qty_df.index)

        for _sub_qty_df in [exec_qty_df, transfer_qty_df]:
            if not _sub_qty_df.empty:
                start_candi.append(_sub_qty_df.index[0])
                end_candi.append(_sub_qty_df.index[-1])

        qty_tickers = set(exec_qty_df.columns) | set(transfer_qty_df.columns)
        end_candi = [to_date or max(end_candi)]

        if not last_registered.empty:
            last_registered = last_registered[last_registered > 0]
            qty_tickers = qty_tickers | set(last_registered.columns)

        if not qty_tickers:
            raise PreconditionFailed("No execution and transfer and registered")

        _start, _end = min(start_candi), max(end_candi)
        if _start == _end:
            raise DuplicateAccess("Already registered")

        qty_df_index = pd.date_range(start=_start, end=_end)
        holding_qty_df = pd.DataFrame(0, columns=list(qty_tickers), index=qty_df_index)

        holding_qty_df.loc[exec_qty_df.index, exec_qty_df.columns] += exec_qty_df
        holding_qty_df.loc[transfer_qty_df.index, transfer_qty_df.columns] += transfer_qty_df
        holding_qty_df = holding_qty_df.tz_localize(settings.TIME_ZONE)

        if last_registered.empty:
            return holding_qty_df.cumsum(axis=0)
        else:
            holding_qty_df.loc[last_registered.index, last_registered.columns] += last_registered
            return holding_qty_df.loc[last_registered_idx:].cumsum(axis=0).iloc[1:]

    def to_representation(self, instance):
        return {'created': len(instance)}


class DailyBalanceSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(help_text="기준일")

    class Meta:
        model = DailyBalance
        fields = '__all__'


class DailyBalanceCreateSerializer(serializers.Serializer):
    account_alias = serializers.CharField(help_text="계좌대체번호")



class SuspensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['account_alias', 'status']


class PensionSerializer(serializers.Serializer):
    account_alias = serializers.CharField(help_text="계좌대체번호")
    base = serializers.IntegerField(help_text="투자원금")
    balance = serializers.IntegerField(help_text="평가금")


class TradeDataCreateSerializer(serializers.Serializer):
    trd_date = serializers.CharField()
    ord_no = serializers.IntegerField()
    # quantity = serializers.DecimalField(default=0, max_digits=30, decimal_places=6, allow_null=True)
    deposit_amt = serializers.IntegerField(default=0)
    commission = serializers.IntegerField(default=0)
    in_come_tax = serializers.IntegerField(default=0)
    currency_name = serializers.CharField(default='')
    pre_p_deposit = serializers.IntegerField(default=0)
    ex_deposit = serializers.FloatField(default=0.0)
    j_name = serializers.CharField(default='', max_length=35)
    settled_amt = serializers.IntegerField(default=0)
    trd_p = serializers.CharField(default='', allow_null=True, allow_blank=True)
    trd_tax = serializers.DecimalField(default=0, max_digits=30, decimal_places=10)
    reside_tax = serializers.IntegerField(default=0)
    perfor_qty = serializers.DecimalField(default=0, max_digits=30, decimal_places=10)
    ex_chg_rate = serializers.FloatField(default=0.0)
    pre_pay_repay = serializers.IntegerField(default=0)
    stock_name = serializers.CharField(default='', allow_blank=True)
    trd_amt = serializers.CharField(default='')
    agr_tax = serializers.IntegerField(default=0)
    unpaid_repay = serializers.IntegerField(default=0)
    etc_repay = serializers.IntegerField(default=0)
    stock_qtry = serializers.DecimalField(default=0, max_digits=30, decimal_places=10)
    for_comm_r = serializers.FloatField(default=0.0)
    for_amt_r = serializers.FloatField(default=0.0)
    st_stock_code = serializers.CharField(default='', allow_blank=True)
    for_amt = serializers.IntegerField(default=0)
    j_code = serializers.CharField(default='', max_length=3)

    def to_representation(self, instance):
        instance['trd_date'] = self.convert_trd_date(instance['trd_date'])
        instance['trd_amt'] = self.convert_trd_amt(instance['trd_amt'])
        instance['trd_p'] = self.convert_trd_p(instance['trd_p'])
        return instance

    def convert_trd_date(self, trd_date):
        return trd_date[:4] + '-' + trd_date[4:6] + '-' + trd_date[6:]

    def convert_trd_amt(self, trd_amt):
        return Decimal(trd_amt.replace(',', '')) if trd_amt else 0

    def convert_trd_p(self, trd_p):
        return Decimal(trd_p.replace(',', '')) if trd_p else 0


class ExecutionDataCreateSerializer(serializers.Serializer):
    order_date = serializers.CharField(default='', help_text='체결일자')
    ord_no = serializers.IntegerField(default='', help_text="주문번호")
    code_name = serializers.CharField(default='', help_text="종목명")
    code = serializers.CharField(default='', help_text="단축종목코드")
    trade_sec_name = serializers.CharField(default='', help_text="거래구분명")
    order_status = serializers.CharField(default='', help_text="주문상태명")
    exec_qty = serializers.DecimalField(default=0, help_text="체결수량", max_digits=26, decimal_places=6)
    exec_price = serializers.DecimalField(default=0, help_text="체결가격", max_digits=15, decimal_places=6)
    ord_qty = serializers.DecimalField(default=0, help_text="주문수량",  max_digits=26, decimal_places=6)
    ord_price = serializers.DecimalField(default=0, help_text="주문가격", max_digits=15, decimal_places=6)
    unexec_qty = serializers.DecimalField(default=0, help_text="미체결수량", max_digits=26, decimal_places=6)
    org_ord_no = serializers.IntegerField(default=0, help_text="원주문번호")
    mkt_clsf_nm = serializers.CharField(default='', help_text="시장구분명")
    currency_code = serializers.CharField(default='', help_text="통화코드")
    ord_sec_name = serializers.CharField(default='', help_text="주문구분명")
    from_time = serializers.HiddenField(default=None, help_text="시작시간")
    to_time = serializers.HiddenField(default=None, help_text="종료시간")
    order_tool_name = serializers.CharField(default='', help_text="주문매체명")
    order_time = serializers.CharField(default='', help_text="주문시간")
    aplc_excj_rate = serializers.DecimalField(default=0, help_text="적용환율", max_digits=9, decimal_places=4)
    reject_reason = serializers.CharField(default='', help_text="거부사유")
    ex_code = serializers.CharField(default='', help_text="해외거래소구분코드")
    loan_date = serializers.CharField(default='', help_text="대출일자")
    org_price = serializers.DecimalField(default=0, help_text="주문가격", max_digits=15, decimal_places=4)
    exchange_rate = serializers.DecimalField(default=0, help_text="환율", max_digits=9, decimal_places=4)
    frgn_stp_prc = serializers.DecimalField(default=0, help_text="해외중단가격(P4)", max_digits=16, decimal_places=4)
    frgn_brkr_ccd = serializers.CharField(default='', help_text="해외브로커구분코드")

    def to_representation(self, instance):
        instance['order_date'] = self.convert_order_date(instance['order_date'])
        instance['order_time'] = self.convert_order_time(instance['order_time'])
        return instance

    def convert_order_date(self, order_date):
        return order_date[:4] + '-' + order_date[4:6] + '-' + order_date[6:]

    def convert_order_time(self, order_time):
        return order_time[:2] + ':' + order_time[2:4] + ':' + order_time[4:]


class AccAmountRechecktHistorySerializer(serializers.Serializer):
    base_amt = serializers.SerializerMethodField(help_text="입출금 원금")
    input_amt = serializers.IntegerField(default=0, help_text="입금액")
    output_amt = serializers.IntegerField(default=0, help_text="출금액")
    input_usd_amt = serializers.IntegerField(default=0, help_text="외화 입금액")
    output_usd_amt = serializers.IntegerField(default=0, help_text="외화 출금액")

    transfer_amt = serializers.SerializerMethodField(help_text="입출고액")
    import_amt = serializers.SerializerMethodField(default=0, help_text="입고액")
    export_amt = serializers.SerializerMethodField(default=0, help_text="출고액")

    dividend_amt = serializers.SerializerMethodField(help_text="배당금(세후)")
    pretax_dividend_amt = serializers.SerializerMethodField(help_text="배당금(세전)")
    dividend_tax_amt = serializers.SerializerMethodField(help_text="배당금 원천세")
    dividend_input_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="배당입금액(세전)")
    dividend_output_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="배당출금액(세전)")
    oversea_tax_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="배당금 원천세 출금액")
    oversea_tax_refund_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15,
                                                      help_text="배당금 원천세 반환금")

    stock_transfer_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="입출고 총계")
    stock_import_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="입고 총계")
    stock_export_amt = serializers.DecimalField(default=0, decimal_places=4, max_digits=15, help_text="출고 총계")


    def get_base_amt(self, attrs) -> Decimal:
        acc_input_amt, acc_output_amt = 0, 0
        for k in ['input_amt', 'stock_import_amt', 'input_usd_amt']:
            acc_input_amt += attrs.get(k, 0)

        for k in ['output_amt', 'stock_export_amt', 'output_usd_amt']:
            acc_output_amt += attrs.get(k, 0)
        return Decimal(acc_input_amt - acc_output_amt)

    def get_pretax_dividend_amt(self, attrs):
        pretax_dividend = attrs.get('dividend_input_amt', 0) - attrs.get('dividend_output_amt', 0)
        return Decimal(round(pretax_dividend, 2))

    def get_dividend_tax_amt(self, attrs):
        return Decimal(round(attrs.get('oversea_tax_amt', 0) - attrs.get('oversea_tax_refund_amt', 0), 2))

    def get_dividend_amt(self, attrs) -> Decimal:
        pretax_dividend = self.get_pretax_dividend_amt(attrs)
        tax = self.get_dividend_tax_amt(attrs)
        return Decimal(round(pretax_dividend - tax, 2))

    def get_import_amt(self, attrs):
        return attrs.get('stock_import_amt', 0)

    def get_export_amt(self, attrs):
        return attrs.get('stock_export_amt', 0)

    def get_transfer_amt(self, attrs) -> int:
        return attrs.get('stock_transfer_amt', 0)

    def to_internal_value(self, data):
        data['input_amt'] = data['input_amt'] - data['input_usd_amt']
        data['output_amt'] = data['output_amt'] - data['output_usd_amt']
        return data

    class Meta:
        model = AmountHistory
        fields = (
            'base_amt',
            'input_amt', 'output_amt', 'input_usd_amt', 'output_usd_amt',
            'import_amt', 'export_amt', 'transfer_amt',
            'dividend_amt', 'dividend_input_amt', 'dividend_output_amt', 'oversea_tax_amt', 'oversea_tax_refund_amt',
            'pretax_dividend_amt', 'dividend_tax_amt'
        )
