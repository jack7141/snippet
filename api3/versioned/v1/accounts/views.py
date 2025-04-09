import datetime
import logging

import pandas as pd
from celery import current_app
from django.db import transaction
from django.db.models import Avg
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, mixins, status, exceptions
from rest_framework.generics import get_object_or_404
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from api.bases.accounts.calcuator import BaseAmountCalculator
from api.bases.accounts.models import (
    Account, Asset, AssetDetail, AmountHistory,
    Execution, Trade, Settlement, Holding, SumUp,
)
from api.bases.accounts.tasks import recalculate_amount
from api.bases.forex.models import ExchangeRate
from api.bases.infomax.models import ClosingPrice
from api.bases.orders.models import Event
from common.exceptions import PreconditionFailed, ConflictException
from common.orm_utils import bulk_create_or_update
from common.utils import get_datetime_kst
from common.viewsets import MappingViewSetMixin
from .filters import (
    AccountAliasFilterSet, PeriodFilterSet,
    DumpAccountFilterSet, TradePeriodFilterSet, ExecutionPeriodFilterSet, SumUpNameFilterSet,
    MappingDjangoFilterBackend, AssetPeriodFilterSet
)
from .serializers import (
    AccountSerializer, AccountUpdateSerializer,
    AssetSerializer, AssetDetailSerializer,
    AmountHistorySerializer, AmountHistoryCreateSerializer, AccAmountHistorySerializer,
    AmountHistoryUpdateInputSerializer, AmountHistoryUpdateSerializer, AmountHistoryQueueCreateSerializer,
    AccountDumpInputSerializer, AccountAssetDumpSerializer,
    AccountTradeSerializer,
    AccountExecutionSerializer,
    TradeAmountSerializer,
    SumUpSerializer,
    SumUpUpdateSerializer,
    SettlementSerializer,
    SettlementCreateSerializer,
    SettlementUpdateSerializer,
    HoldingSerializer,
    HoldingCreateSerializer,
    DailyBalanceSerializer,
    DailyBalanceCreateSerializer,
    SuspensionSerializer,
    PensionSerializer,
    AccountPensionDumpInputSerializer, TradeDataCreateSerializer, ExecutionDataCreateSerializer,
    AccAmountRechecktHistorySerializer
)

logger = logging.getLogger('django.server')

BID = '매수'
ASK = '매도'


class AccountViewSet(MappingViewSetMixin,
                     viewsets.ModelViewSet):
    """
    retrieve:계좌 상세조회

    계좌 상세정보를 조회합니다.
    ---

    list:전체 계좌 목록 조회 API

    전체 계좌목록을 조회합니다.
    ---

    create:계좌 생성 API

    계좌를 생성합니다.
    ---

    partial_update:계좌 정보 수정 API

    ---
    계좌 정보를 수정합니다.

    수정 가능 field 값
    - status
    - risk_type

    destroy:계좌 해지처리 요청

    요청 받은 계좌에 대해 해지 프로세스를 진행합니다.
    정상 계좌 + 주문완료 이력 있음 -> 해지 매도 대기중
    정상 계좌 + 주문완료 이력 없음 -> 해지됨
    환전 완료 -> 해지됨
    ---
    """
    queryset = Account.objects.all().order_by('created_at')
    serializer_class = AccountSerializer
    serializer_action_map = {
        'partial_update': AccountUpdateSerializer
    }
    filter_fields = ('vendor_code', 'status', 'account_type', 'risk_type', 'strategy_code')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        # 이미 닫힌 계좌
        if instance.status == Account.STATUS.canceled:
            raise ConflictException(f"account is already closed")

        # 계좌가 해지 진행중인 경우
        if instance.status in [
            Account.STATUS.account_sell_reg,
            Account.STATUS.account_sell_f1,
            Account.STATUS.account_sell_s,
            Account.STATUS.account_exchange_reg,
            Account.STATUS.account_exchange_f1
        ]:
            raise ConflictException(f"account is being closed")

        # 정상 계좌 케이스
        if instance.status == Account.STATUS.normal:
            event_queryset = instance.event_set

            # 주문 여부 확인
            if event_queryset.exists():
                if event_queryset.filter(status=Event.STATUS.completed).exists():
                    instance.status = Account.STATUS.account_sell_reg
                else:
                    raise PreconditionFailed(f"account must have a completed order to register sell if order exist")
            else:
                instance.status = Account.STATUS.canceled

        # 환전완료 -> 해지됨 처리
        elif instance.status == Account.STATUS.account_exchange_s:
            instance.status = Account.STATUS.canceled
        else:
            raise PreconditionFailed(f"account status must be normal to close")
        instance.save()


class AccountCleanUpViewSet(MappingViewSetMixin,
                            mixins.ListModelMixin,
                            mixins.DestroyModelMixin,
                            viewsets.GenericViewSet):
    """
    list:비활성화된 계좌 목록 조회 API

    비활성화된 계좌목록을 조회합니다.
    ---

    destroy:계좌 비활성화 계좌 삭제 API

    비활성화된 계좌를 삭제합니다.
    ---
    """

    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    filter_fields = ['vendor_code']

    def destroy(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = AccountSerializer(queryset, many=True)
        response_data = serializer.data
        self.perform_destroy(queryset)
        return Response(response_data, status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        return self.queryset.filter(status=Account.STATUS.canceled).order_by('account_alias')


class AccountDumpViewSet(MappingViewSetMixin, viewsets.GenericViewSet):
    """
    dump:계좌목록 dump API

    계좌목록 Dump 데이터 목록을 조회합니다.
    ---

    - date: 기준일 이전에 생성된 전체 계약 목록을 조회합니다.
    (주문대리인 미등록시, 해당 dump data로는 계좌 조회가 불가능하여 배치로 적재가 불가함)

    dump_assets: 계좌 Asset 데이터 dump API

    전체 계좌(미해지 계좌대상) Asset 목록을 조회합니다.
    ---

    dump_pension: 계좌 Pension 데이터 dump API

    전체 계좌(미해지 계좌대상) Pension 목록을 조회합니다.
    ---
    """

    serializer_class = AccountDumpInputSerializer
    serializer_action_map = {
        'dump_assets': AccountDumpInputSerializer,
        'dump_pension': AccountPensionDumpInputSerializer
    }
    queryset = Account.objects.exclude(status=Account.STATUS.canceled).filter(type=0)
    queryset_map = {
        'dump_pension': Account.objects.exclude(status=Account.STATUS.canceled).filter(type__in=[2, 21])
    }
    renderer_classes = [JSONRenderer, ]
    pagination_class = None
    filterset_class = DumpAccountFilterSet

    def dump(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        date = self.request.parser_context.get('date')
        vendor_code = self.request.parser_context.get('vendor_code', 'kb')
        serializer = self.get_serializer({'account_list': queryset, 'date': date, 'vendor_code': vendor_code})
        return Response(serializer.data)

    @swagger_auto_schema(manual_parameters=[openapi.Parameter(name='task_size', in_=openapi.IN_QUERY,
                                                              required=False, type=openapi.TYPE_INTEGER)])
    def dump_assets(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        target_date = self.request.parser_context.get('date')
        input_serializer = self.get_serializer({'account_list': queryset, 'date': target_date})
        output_serializer = AccountAssetDumpSerializer(data=input_serializer.data, context=request.query_params.dict())
        output_serializer.is_valid(raise_exception=True)
        return Response(output_serializer.data)

    def dump_pension(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        date = self.request.parser_context.get('date')
        serializer = self.get_serializer({'account_list': queryset, 'date': date})
        return Response(serializer.data)


class AssetViewSet(viewsets.ReadOnlyModelViewSet, MappingDjangoFilterBackend):
    """
    list:전체 자산 목록 조회 API

    전체 계좌의 자산 정보 목록을 조회합니다.
    ---

    retrieve:자산 정보 조회 API

    계좌의 자산 정보를 조회합니다.
    ---
    calc_quarter: 연금 계좌의 지정한 날짜의 평균값을 계산하여 반환합니다.

    운용 중지된 계좌 목록을 조회합니다.

    ---

    - key: account_alias
    """

    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    filter_fields = ('account_alias',)
    filter_action_map = {
        'retrieve': AccountAliasFilterSet,
        'calc_quarter': AssetPeriodFilterSet,
    }

    def calc_quarter(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        base_avg = queryset.aggregate(Avg('base')).get('base__avg')
        return Response({'avg': base_avg}, status=status.HTTP_200_OK)


class AssetDetailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list:전체 계좌의 자산 상세조회 API

    전체 계좌의 자산 상세정보를 조회합니다.
    ---

    retrieve:자산 상세 정보 조회 API

    계좌의 상세 자산 정보를 조회합니다.
    ---

    - key: account_alias
    """
    queryset = AssetDetail.objects.all()
    serializer_class = AssetDetailSerializer
    filter_fields = ('account_alias', 'code')


class AmountViewSet(MappingViewSetMixin,
                    mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin,
                    mixins.ListModelMixin,
                    mixins.UpdateModelMixin,
                    viewsets.GenericViewSet):
    """
    list:입출금 내역 조회

    일별 입출금 내역을 조회합니다.
    ---

    retrieve:계좌 기간 누적 입출금 조회

    해당 계좌의 기간 누적 입출금액을 조회합니다.
    ---

    create: 계좌 입출금 내역 정산

    해당 계좌의 기간 입출금액을 정산합니다.
    ---

    partial_update:입출금 내역 재정산

    해당 계좌의 기간 입출금액을 재정산합니다.
    ---

    create_queue:입출금 재정산 Queue 생성

    특정 조건의 입출금 재정산 Task를 생성합니다.
    ---

    get_queue_state:입출금 재정산 Queue State 조회

    재정산 Queue의 state를 조회합니다.
    ---
    """
    queryset = AmountHistory.objects.all()
    serializer_class = AmountHistorySerializer
    filterset_class = PeriodFilterSet

    serializer_action_map = {
        'create': AmountHistoryCreateSerializer,
        'partial_update': AmountHistoryUpdateInputSerializer,
        'create_queue': AmountHistoryQueueCreateSerializer
    }
    queryset_map = {
        'retrieve': Account.objects.all(),
        'partial_update': Account.objects.all(),
        'check_amount': Account.objects.all()
    }

    @swagger_auto_schema(manual_parameters=[openapi.Parameter(name='from_date', in_=openapi.IN_QUERY,
                                                              required=False, type=openapi.FORMAT_DATE,
                                                              format=openapi.FORMAT_DATE),
                                            openapi.Parameter(name='to_date', in_=openapi.IN_QUERY,
                                                              required=False, type=openapi.FORMAT_DATE,
                                                              format=openapi.FORMAT_DATE)])
    def retrieve(self, request, from_date=None, to_date=None, *args, **kwargs):
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_field]}
        acct = Account.objects.get_or_404_raise(filter_kwargs)
        try:
            serializer = AccAmountHistorySerializer(data=acct.get_period_amount(**self.request.query_params.dict()))
        except ValueError as e:
            raise exceptions.ValidationError({"detail": e})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        filter_kwargs = {self.lookup_field: self.kwargs[self.lookup_field]}
        acct = get_object_or_404(self.get_queryset(), **filter_kwargs)
        if not acct.amounthistory_set.exists():
            raise PreconditionFailed("Matched AmountHistory can't find to update")

        diffs = AmountHistoryUpdateSerializer.get_diffs(acct=acct, queryset=acct.amounthistory_set)
        for i, row in diffs.iterrows():
            instance = acct.amounthistory_set.get(account_alias=acct, created_at=get_datetime_kst(i))
            serializer = AmountHistoryUpdateSerializer(instance, data=row.to_dict())
            serializer.is_valid(raise_exception=True)
            serializer.save()
        return Response({'updated': len(diffs)})

    def create_queue(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        task = recalculate_amount.apply_async(kwargs=s.data, expires=60)
        return Response({'task_id': task.id, 'status': task.state}, status=status.HTTP_202_ACCEPTED)

    def get_queue_state(self, request, task_id, *args, **kwargs):
        async_result = current_app.AsyncResult(task_id)
        result = None
        if async_result.state == 'SUCCESS':
            result = async_result.get()
        return Response({'task_id': task_id, 'status': async_result.state, 'result': result})

    def check_amount(self, request, account_alias, *args, **kwargs):
        filter_kwargs = {self.lookup_field: account_alias}
        acct = Account.objects.get_or_404_raise(filter_kwargs)
        serializer = AccAmountRechecktHistorySerializer(data=acct.get_amount(**self.request.query_params.dict()))
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class AccountTradeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    retrieve:거래내역 조회

    ---

    list:거래목록 조회

    ---
    """
    queryset = Trade.objects.all()
    serializer_class = AccountTradeSerializer
    filterset_class = TradePeriodFilterSet
    filter_fields = ('account_ailas',)

    def filter_queryset(self, queryset):
        queryset = queryset.filter(**self.kwargs)
        queryset = super().filter_queryset(queryset=queryset)
        return queryset

    def create(self, request, *args, **kwargs):
        acct = Account.objects.get(account_alias=request.data['account_alias'])

        serializer = TradeDataCreateSerializer(data=request.data['trades'], many=True)
        serializer.is_valid(raise_exception=True)

        bulk_create_objs = [Trade(account_alias=acct, **trade) for trade in serializer.data]

        created, updated = bulk_create_or_update(model_class=Trade, objs=bulk_create_objs,
                                        match_field_names=['account_alias', 'trd_date', 'ord_no'],
                                        exclude_field_names=['id', 'account_alias', 'trd_date', 'ord_no'])

        return Response({'created': created, 'updated': updated}, status=status.HTTP_201_CREATED)


class AccountTradeSumUpViewSet(MappingViewSetMixin,
                               mixins.CreateModelMixin,
                               mixins.ListModelMixin,
                               mixins.UpdateModelMixin,
                               viewsets.GenericViewSet):
    """
    list:거래 적요 목록 조회

    적요 목록을 조회합니다.
    ---

    create:거래 적요 등록

    적요 수정합니다.
    ---

    partial_update:거래 적요 수정

    등록된 적요 내용을 수정합니다.
    ---

    get_j_names:거래 적요명 목록 조회

    등록된 적요명 목록을 조회합니다.
    ---

    get_amount_func_types:정산 그룹별 적요명 조회

    정산 대상별 적요명을 조회합니다.
    ---

    get_trade_types:거래 그룹별 적요명 조회

    거래 그룹별 적요명을 조회합니다.
    ---
    """
    queryset = SumUp.objects.all()
    filterset_class = SumUpNameFilterSet
    serializer_class = SumUpSerializer
    serializer_action_map = {
        'partial_update': SumUpUpdateSerializer
    }

    def get_j_names(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        return Response(queryset.values_list('j_name', flat=True))

    def get_amount_func_types(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        return Response(SumUp.get_amount_func_types(queryset=qs))

    def get_trade_types(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        return Response(SumUp.get_trade_types(queryset=qs))


class AccountExecutionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    retrieve:체결내역 조회

    ---

    list:체결목록 조회

    ---
    """
    queryset = Execution.objects.all()
    serializer_class = AccountExecutionSerializer
    lookup_field = 'account_alias'
    filterset_class = ExecutionPeriodFilterSet

    def filter_queryset(self, queryset):
        queryset = queryset.filter(**self.kwargs)
        queryset = super().filter_queryset(queryset=queryset)
        return queryset

    def create(self, request, *args, **kwargs):
        acct = Account.objects.get(account_alias=request.data['account_alias'])

        serializer = ExecutionDataCreateSerializer(data=request.data['trades'], many=True)
        serializer.is_valid(raise_exception=True)

        bulk_create_objs = [Execution(account_alias=acct, **execution) for execution in serializer.data]

        created, updated = bulk_create_or_update(model_class=Execution, objs=bulk_create_objs,
                                        match_field_names=['account_alias', 'order_date', 'ord_no'],
                                        exclude_field_names=['id', 'account_alias', 'order_date', 'ord_no'])

        return Response({'created': created, 'updated': updated}, status=status.HTTP_201_CREATED)


class AccountTradeAmountViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list:계좌 거래내역 조회

    ---

    calc_amount:기간 누적 거래 총계 조회

    ---
    """
    queryset = Trade.objects.all()
    serializer_class = TradeAmountSerializer
    lookup_field = 'account_alias'
    filterset_class = TradePeriodFilterSet

    def filter_queryset(self, queryset):
        queryset = queryset.filter(**self.kwargs)
        queryset = super().filter_queryset(queryset=queryset)
        return queryset

    def calc_amount(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        to_date_query_param = {'trd_date__lte': v for k, v in self.request.query_params.items() if k in ['to_date']}
        cum_df = pd.DataFrame(queryset.filter(**self.kwargs, **to_date_query_param).values())
        queryset = self.filter_queryset(queryset)
        period_df = pd.DataFrame(queryset.values())

        period_base_calculator = BaseAmountCalculator(trade_df=period_df)
        period_resp = period_base_calculator.calculate()
        cum_base_calculator = BaseAmountCalculator(trade_df=cum_df)
        cum_resp = cum_base_calculator.calculate()

        serializer = self.get_serializer({'cum': cum_resp, 'period': period_resp})
        return Response(serializer.data)


class SettlementViewSet(MappingViewSetMixin,
                        mixins.ListModelMixin,
                        mixins.CreateModelMixin,
                        mixins.UpdateModelMixin,
                        viewsets.GenericViewSet):
    """
    create: 계좌 정산 데이터 생성

    ---

   list: 계좌 정산 내역 조회

    ---

    update: 계좌 정산 데이터 재생성

    ---
    """

    serializer_class = SettlementSerializer
    serializer_action_map = {
        'create': SettlementCreateSerializer,
        'partial_update': SettlementUpdateSerializer,
    }
    queryset = Settlement.objects.all()

    def filter_queryset(self, queryset):
        queryset = queryset.filter(**self.kwargs)
        queryset = super().filter_queryset(queryset=queryset)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        acct = Account.objects.get(account_alias=serializer.validated_data['account_alias'])
        instances = Settlement.objects.settle(account_alias_id=acct.account_alias,
                                              to_date=serializer.data.get('to_date'), use_registered=True)
        created = Settlement.objects.bulk_create(instances)
        return Response({'created': len(created)}, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        acct = self.get_object()

        instances = Settlement.objects.settle(account_alias_id=acct.account_alias,
                                              to_date=serializer.data.get('to_date'), use_registered=False)
        with transaction.atomic():
            Settlement.objects.filter(account_alias_id=acct.account_alias).delete()
            created = Settlement.objects.bulk_create(instances)
        return Response({'created': len(created)}, status=status.HTTP_200_OK)


class HoldingViewSet(MappingViewSetMixin,
                     mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     viewsets.GenericViewSet):
    """
    list: 보유수량 조회

    ---

    create: 보유수량 정산

    ---

    update: 보유수량 재정산

    ---
    """

    serializer_action_map = {
        'create': HoldingCreateSerializer,
        'partial_update': HoldingCreateSerializer,
    }
    serializer_class = HoldingSerializer
    queryset = Holding.objects.all()
    filterset_class = PeriodFilterSet


class DailyBalanceViewSet(MappingViewSetMixin,
                          viewsets.ModelViewSet):
    queryset = Settlement.objects.all()
    serializer_class = SettlementSerializer
    filter_class = AccountAliasFilterSet
    lookup_field = 'account_alias_id'
    serializer_action_map = {
        'create': DailyBalanceCreateSerializer
    }

    def calc_balance(self, account_alias_id):
        holding_queryset = Holding.objects.filter(account_alias_id=account_alias_id)
        price_queryset = ClosingPrice.objects.filter(symbol__in=list(holding_queryset.values_list('code', flat=True)))
        balance_sr = holding_queryset.calc_balance_usd(price_queryset)

        if not balance_sr.empty:
            from_date, to_date = balance_sr.index[0], balance_sr.index[-1]
            exchange_rate_df = ExchangeRate.objects.filter(base_date__gte=from_date, base_date__lte=to_date).to_df(
                'open')
            exchange_rate_df.index = exchange_rate_df.index.shift(1, 'D')
            balance_sr = (balance_sr * exchange_rate_df.USD.astype(float)).round(0)
        return balance_sr

    def retrieve(self, request, *args, **kwargs):
        daily_balance_sr = self.calc_balance(**kwargs)
        daily_balance_sr.index = daily_balance_sr.index.strftime('%Y-%m-%d')
        return Response(daily_balance_sr.round(2).to_dict())

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        daily_balance_df = self.calc_balance(account_alias_id=serializer.validated_data['account_alias'])
        daily_balance_serializer = DailyBalanceSerializer(data=daily_balance_df.to_dict(orient='records'), many=True)
        daily_balance_serializer.is_valid(raise_exception=True)
        self.perform_create(daily_balance_serializer)
        headers = self.get_success_headers(daily_balance_serializer.data)
        return Response(daily_balance_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class AccountAssetViewSet(viewsets.ModelViewSet):
    """
    calc_asset: 계좌 Asset 데이터 재정산 API

    계좌 Asset 데이터 재정산 API입니다.

    """

    queryset = Trade.objects.all()
    lookup_field = 'account_alias_id'

    def filter_queryset(self, queryset):
        queryset = queryset.filter(**self.kwargs)
        queryset = super().filter_queryset(queryset=queryset)
        return queryset

    def calc_asset(self, request, *args, **kwargs):
        """타겟 계좌의 전일자 예수금과 투자원금을 재계산하고 재적재하여 DB에 반영합니다."""
        queryset = self.filter_queryset(self.get_queryset())

        trade_df = queryset.values()
        acct = Account.objects.get(account_alias=kwargs['account_alias_id'])
        prev_deposit_calculator = BaseAmountCalculator(acct=acct, trade_df=trade_df)
        prev_deposits = prev_deposit_calculator.asset_prev_calculate()

        target_asset = Asset.objects.filter(account_alias=self.kwargs.get(self.lookup_field))

        prev_asset = target_asset

        for trd_date, prev_deposit in prev_deposits.items():
            target_asset.filter(created_at__year=trd_date.year,
                                created_at__month=trd_date.month,
                                created_at__day=trd_date.day).update(prev_deposit=prev_deposit)

        _base = 0
        for value in target_asset.values():
            trd_date = value.get('created_at')
            prev_deposit = value.get('prev_deposit')
            _base += prev_deposit
            target_asset.filter(created_at__year=trd_date.year,
                                created_at__month=trd_date.month,
                                created_at__day=trd_date.day).update(base=_base)

        return Response({'prev_base': prev_asset.values(), 'update_base': target_asset.values()})


class SuspensionAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list:운용중지 계좌 목록 조회
    운용 중지된 계좌 목록을 조회합니다.
    ---
    retrieve:운용 중지 계좌 상세 조회
    해당 운용 중지 계좌를 상세 조회합니다.
    ---
    """
    serializer_class = SuspensionSerializer
    queryset = Account.objects.filter(status=Account.STATUS.account_suspension)


class PensionViewSet(MappingViewSetMixin,
                     mixins.CreateModelMixin,
                     viewsets.GenericViewSet):
    """
    create: 계좌의 원금과 평가금 차액 계산

    연금 이전이 완료된 계좌의 원금과 평가금 차액을 저장합니다.
    ---
    """
    serializer_class = PensionSerializer
    queryset = Account.objects.filter(type__in=[2, 21])

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        acct = Account.objects.filter(account_alias=serializer.validated_data['account_alias'])
        diff = request.data['base'] - request.data['balance']
        acct.update(pension_base_diff=diff)
        return Response({'created': acct.values()}, status = status.HTTP_201_CREATED)

