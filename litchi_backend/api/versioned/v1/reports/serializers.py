import ast
import pytz

from django.utils import timezone
from dateutil import parser as date_parser
from datetime import datetime, timedelta
from rest_framework import serializers
from common.exceptions import PreconditionRequired
from common.utils import to_kst
from api.bases.contracts.models import Contract
from api.bases.reports.models import (
    ManagementReportHeader, AssetUniverse, RoboAdvisorDesc, ManagerDetail,
    ManagementReport, TradingDetail, HoldingDetail, Performance
)


def to_kst(dt: datetime, oclock=False):
    if oclock:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

    kst_tz = pytz.timezone('Asia/Seoul')
    if timezone.is_aware(dt):
        return timezone.localtime(dt, kst_tz)
    return timezone.make_aware(dt, kst_tz)


class ManagementReportHeaderRetrieveMixin(serializers.Serializer):
    year = serializers.CharField(max_length=4, help_text="기준년도", write_only=True)
    quarter = serializers.CharField(max_length=4, help_text="기준분기", write_only=True)
    strategy_code = serializers.IntegerField(help_text="전략구분", write_only=True)

    def get_report_header(self, year, quarter, strategy_code):
        return ManagementReportHeader.objects.get(year=year, quarter=quarter, strategy_code=strategy_code)


class ManagementReportHeaderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManagementReportHeader
        fields = "__all__"


class ManagementReportHeaderDetailSerializer(ManagementReportHeaderSerializer):
    nested_field_map = {
        'roboadvisordesc': 'ra_desc',
        'managerdetail_set': 'managers',
        'assetuniverse_set': 'universes'
    }

    class Meta:
        model = ManagementReportHeader
        fields = "__all__"

    class _ManagementReportHeaderManagerDetailSerializer(serializers.ModelSerializer):
        class Meta:
            model = ManagerDetail
            exclude = ('id', 'year', 'quarter', 'strategy_code', 'created_at', 'updated_at')

        career = serializers.SerializerMethodField(help_text="경력 상세")

        def get_career(self, instance):
            return ast.literal_eval(instance.career)

    class _ManagementReportHeaderRoboAdvisorDescSerializer(serializers.ModelSerializer):
        class Meta:
            model = RoboAdvisorDesc
            exclude = ('id', 'year', 'quarter', 'strategy_code', 'created_at', 'updated_at')

        inception_date = serializers.DateTimeField(format="%Y-%m-%d")

    class _ManagementReportAssetUniverseSerializer(serializers.ModelSerializer):
        class Meta:
            model = AssetUniverse
            exclude = ('id', 'year', 'quarter', 'created_at', 'updated_at')

    ra_desc = _ManagementReportHeaderRoboAdvisorDescSerializer(source='get_ra_desc')
    managers = _ManagementReportHeaderManagerDetailSerializer(many=True, source='get_manager_details')
    universe = _ManagementReportAssetUniverseSerializer(many=True, source='get_universe')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['universe'] = {_asset['code']: {k: v for k, v in _asset.items() if k not in ['code']}
                                      for _asset in representation['universe']}
        return representation


class ReportContractDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ("id", "account_number", "status", "effective_date",)


class ManagementReportSerializer(ManagementReportHeaderRetrieveMixin, serializers.ModelSerializer):
    class Meta:
        model = ManagementReport
        fields = "__all__"

    header = ManagementReportHeaderSerializer(source='get_header')
    baseline_date = serializers.DateTimeField(format='%Y-%m-%d', help_text='조회기준일')
    qtr_commission = serializers.IntegerField(help_text="해당 분기 매매 수수료")
    qtr_tax = serializers.IntegerField(help_text="해당분기 각종세금(제세금, 배당에 대한 해외 원천세 포함)")
    qtr_other_cost = serializers.IntegerField(help_text="해당 분기 각종비용(제비용)")
    qtr_total_cost = serializers.IntegerField(help_text="해당 분기 총비용")
    cum_commission = serializers.IntegerField(help_text="누적기간 매매수수료")
    cum_tax = serializers.IntegerField(help_text="누적기간 매매수수료(제세금, 배당에 대한 해외 원천세 포함)")
    cum_other_cost = serializers.IntegerField(help_text="누적기간 각종비용(제비용)")
    cum_total_cost = serializers.IntegerField(help_text="누적기간 총비용")
    qtr_buy_amount = serializers.IntegerField(help_text="해당 분기 매수금액 합계(원화기준)")
    qtr_sell_amount = serializers.IntegerField(help_text="해당 분기 매도금액 합계(원화기준)")
    cum_buy_amount = serializers.IntegerField(help_text="누적기간 매수금액 합계(원화기준)")
    cum_sell_amount = serializers.IntegerField(help_text="누적기간 매도금액 합계(원화기준)")


class AccountAmountSerializer(serializers.Serializer):
    base_changed = serializers.FloatField(help_text="기간 원금 중감액", source="baseChanged")
    input_amt = serializers.IntegerField(help_text="기간 원화 입금 총계", source="inputAmt")
    output_amt = serializers.IntegerField(help_text="기간 원화 출금 총계", source="outputAmt")
    dividend_input_amt = serializers.FloatField(help_text="기간 배당금 총계(세전)", source="dividendInputAmt")
    oversea_tax_amt = serializers.FloatField(help_text="기간 해외원천세 총계", source="overseaTaxAmt")
    dividend = serializers.FloatField(help_text="기간 배당금 총계(세후)")
    stock_transfer_amt = serializers.IntegerField(help_text="기간 입출고 총계", source="stockTransferAmt")
    output_usd_amt = serializers.FloatField(help_text="기간 외화 출금 총계", source="outputUsdAmt")
    stock_import_amt = serializers.IntegerField(help_text="기간 입고 총계", source="stockImportAmt")
    stock_export_amt = serializers.IntegerField(help_text="기간 출고 총계", source="stockExportAmt")


class TradingDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingDetail
        exclude = ('id', 'year', 'quarter', 'account_alias_id', 'created_at', 'updated_at')

    trade_amount = serializers.SerializerMethodField(help_text="거래대금")
    trade_date = serializers.DateTimeField(format='%Y-%m-%d', help_text='거래일자')
    trade_price = serializers.IntegerField(help_text='거래단가')
    trade_commission = serializers.IntegerField(help_text='거래수수료')
    trade_tax = serializers.IntegerField(help_text='거래세')

    def get_trade_amount(self, obj):
        if obj.trade_price is None or obj.shares is None:
            return obj.trade_amount
        return int(obj.trade_price) * obj.shares


class HoldingDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = HoldingDetail
        exclude = ('id', 'year', 'quarter', 'account_alias_id', 'created_at', 'updated_at')

    balance = serializers.SerializerMethodField(help_text="평가금액")
    acquisition_price = serializers.IntegerField(help_text='취득단가')
    market_price = serializers.IntegerField(help_text='현재단가')
    gross_loss = serializers.SerializerMethodField(help_text='평가손익')

    def get_balance(self, obj):
        if obj.market_price is None or obj.shares is None:
            return obj.balance
        return int(obj.market_price) * obj.shares

    def get_gross_loss(self, obj):
        if obj.market_price is None or obj.acquisition_price is None:
            return 0
        return int(obj.market_price) - int(obj.acquisition_price)


class QuarterPerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Performance
        exclude = ('id', 'year', 'quarter', 'created_at', 'updated_at')
        extra_kwargs = {
            'account_alias_id': {'read_only': True}
        }

    from_date = serializers.DateTimeField(format='%Y-%m-%d', help_text="조회 시작일")
    to_date = serializers.DateTimeField(format='%Y-%m-%d', help_text="조회 종료일")
    effective_date = serializers.SerializerMethodField()

    def get_effective_date(self, instance: Performance):
        effective_date = to_kst(instance.effective_date, oclock=False).date()
        return effective_date


class ManagementReportDetailSerializer(ManagementReportSerializer):
    header = ManagementReportHeaderDetailSerializer(source='get_header')
    contract = ReportContractDetailSerializer(help_text="계약ID")
    tradings = serializers.SerializerMethodField(help_text="거래내역 (최근순)")
    holdings = serializers.SerializerMethodField(help_text="보유종목 (평가금액순)")
    performance = serializers.SerializerMethodField(help_text="운용성과 요약")
    start_date = serializers.HiddenField(help_text="분기 운용 시작일", default=None)
    end_date = serializers.HiddenField(help_text="분기 운용 종료일", default=None)

    def get_tradings(self, obj):
        qs = TradingDetail.objects.filter(year=obj.year, quarter=obj.quarter,
                                          account_alias_id=obj.account_alias_id).order_by('-trade_date')
        _serializer = TradingDetailSerializer(qs, many=True)
        return _serializer.data

    def get_holdings(self, obj):
        qs = HoldingDetail.objects.filter(year=obj.year, quarter=obj.quarter,
                                          account_alias_id=obj.account_alias_id)
        _serializer = HoldingDetailSerializer(qs, many=True)
        return _serializer.data

    def get_performance(self, obj):
        try:
            instance = Performance.objects.get(year=obj.year, quarter=obj.quarter, account_alias_id=obj.account_alias_id)
            _serializer = QuarterPerformanceSerializer(instance)
            return _serializer.data
        except Performance.DoesNotExist:
            raise PreconditionRequired("Performance data is required")

    def get_start_date(self, obj, effective_date):
        start_month = 3 * (int(obj.quarter) - 1) + 1
        qtr_start_date = datetime(year=int(obj.year), month=int(start_month), day=1)

        start_date_candi = [qtr_start_date.date()]
        if effective_date is not None:
            start_date_candi.append(effective_date)
        start_date = max(start_date_candi)
        return start_date

    def get_end_date(self, obj):
        end_year = int(obj.year)
        quarter = obj.quarter
        end_month = 3 * (int(quarter)) + 1

        if end_month > 12:
            end_month /= 12
            end_year += 1

        qtr_end_date = datetime(year=int(end_year), month=int(end_month), day=1) - timedelta(days=1)
        end_date_candi = [qtr_end_date.date(), obj.baseline_date.date()]
        end_date = min(end_date_candi)
        return end_date

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        effective_date = representation['performance']['effective_date']
        representation['contract']['effective_date'] = effective_date
        representation['start_date'] = self.get_start_date(instance, effective_date=effective_date)
        representation['end_date'] = self.get_end_date(instance)

        if representation['start_date'] < representation['end_date']:
            serializers.ValidationError("start_date must be earlier than end_date")

        representation['holdings'] = sorted(representation['holdings'],
                                            key=lambda x: (x['shares'] or 0) * float(x['balance']), reverse=True)
        return representation
