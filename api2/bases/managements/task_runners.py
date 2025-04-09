from abc import ABC, abstractproperty
from dataclasses import dataclass
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from celery import Task, shared_task
from django.conf import settings
from django.db.models import Max, F, Q, BooleanField, Case, Value, When

from api.bases.accounts.models import Account
from api.bases.managements.components.data_stagers import (
    CachedTickerStager,
    UnsupportedTicker,
)
from api.bases.managements.components.exchange.currencies import ForeignCurrency
from api.bases.managements.components.exchange.exchanger import (
    AbstractCurrencyExchanger,
    CurrencyExchangerForAccountBeingClosed,
    CurrencyExchangerForAccountNormal,
)
from api.bases.managements.components.exchange.target_accounts import (
    get_accounts_being_closed_etf,
    get_accounts_normal_etf,
)
from api.bases.managements.components.state import QueueStatusContext
from api.bases.managements.components.order_reporter import OrderReporter
from api.bases.managements.models import (
    Queue,
    OrderLog,
    OrderReport,
    ErrorSet,
    ErrorOccur,
    ErrorSolved,
)
from api.bases.managements.order_router import OrderManagement, ExecutionManagement
from api.bases.managements.order_router.order_manager import (
    LONG_POSITION,
    SHORT_POSITION,
    TIME_SCHEDULE,
)
from api.bases.orders.models import Event
from common.mixins import PortfolioMapMixin
from common.exceptions import PreconditionFailed, StopOrderOperation, MinBaseViolation
from common.utils import (
    get_us_today_as_kst,
    get_local_today,
    get_us_today,
    get_account_aliases_from_accounts_with_test_account_aliases,
)

logger = logging.getLogger(__name__)

TR_BACKEND = settings.TR_BACKEND
INFOMAX_BACKEND = settings.INFOMAX_BACKEND
MAX_NOTE_SIZE = 100


def stop_account_operation(account_alias: Account or str):
    if isinstance(account_alias, Account):
        account = account_alias
    else:
        account = Account.objects.get(account_alias=account_alias)

    if account.status == Account.STATUS.normal:
        account.status = Account.STATUS.account_suspension
    elif account.status == Account.STATUS.account_sell_reg:
        account.status = Account.STATUS.account_sell_f1
    else:
        raise TypeError(f"{account.status} is not valid to stop operation")
    account.save()
    return account


def update_account_being_closed_status(queue: Queue):
    # 해지 주문 처리가 완료 혹은 이미 처리된 경우
    if queue.is_completed or queue.is_skipped:
        logger.info(
            f"UPDATE Account({queue.account_alias}) status "
            f"{queue.account.status} -> {queue.account.STATUS.account_sell_s}"
        )
        queue.account.status = Account.STATUS.account_sell_s
        queue.account.save()


class OrderQueueRegisterRunner(Task):
    DAILY_ORDER_QUEUES_MAP = {
        Event.MODES.new_order: [Queue.MODES.bid],
        Event.MODES.sell: [Queue.MODES.sell],
        Event.MODES.buy: [Queue.MODES.bid],
        Event.MODES.rebalancing: [Queue.MODES.bid, Queue.MODES.ask],
    }

    def process(
        self,
        account_alias,
        portfolio,
        daily_order_mode,
        exchange_rate,
        vendor_code,
        *args,
        **kwargs,
    ):
        om, order_basket, note = None, None, ""
        summary = pd.DataFrame()
        rebalancing_flag = True

        try:
            om = OrderManagement(
                account_alias=account_alias,
                data_stager=CachedTickerStager(api_url=INFOMAX_BACKEND.API_HOST),
                portfolio=portfolio["port_data"],
                exchange_rate=exchange_rate,
                vendor_code=vendor_code,
                mode=daily_order_mode,
            )
            om.check_min_base()
            rebalancing_flag = om.is_rebalancing_condition_met
            order_basket = om.order_basket
            summary = om.get_summary()

        except UnsupportedTicker as e:
            note = f"운용 중지(미지원 종목 포함): {str(e)}"
            stop_account_operation(account_alias=account_alias)

        except MinBaseViolation as e:
            note = f"운용 중지(최소 원금 위반): {str(e)}"
            stop_account_operation(account_alias=account_alias)

        except StopOrderOperation as e:
            note = str(e)
            stop_account_operation(account_alias=account_alias)

        except Exception as e:
            note = f"error: {str(e)}"

        for _queue_mode in self.DAILY_ORDER_QUEUES_MAP[daily_order_mode]:
            try:
                _order_queue = Queue(
                    account_alias=account_alias,
                    status=Queue.STATUS.pending,
                    mode=_queue_mode,
                    vendor_code=vendor_code
                )

                if daily_order_mode == Event.MODES.rebalancing:
                    if rebalancing_flag:
                        _order_queue.set_order_basket(
                            order_basket=order_basket, note=note
                        )
                    else:
                        _order_queue.status = Queue.STATUS.skipped
                        _order_queue.note = "리밸런싱 조건에 미해당"
                else:
                    _order_queue.set_order_basket(order_basket=order_basket, note=note)
                logger.info(f"register {_order_queue}")
                _order_queue.save(portfolio_id=portfolio["port_seq"])

                if not summary.empty:
                    self.write_summary(
                        order_management=om, queue=_order_queue, summary=summary
                    )
            except Exception as e:
                logger.error(f"{e}")

    @staticmethod
    def write_summary(
        order_management: OrderManagement, queue: Queue, summary: pd.DataFrame
    ):
        order_management.set_reporter(queue=queue)
        weight_column_indexer = summary.columns.str.contains("weight")
        weight_columns = summary.columns[weight_column_indexer]
        non_weight_columns = summary.columns[~weight_column_indexer]
        deposit_info = (1 - summary[weight_columns].sum(axis=0)).round(3)

        order_management.reporter.write_body(
            data=summary[weight_columns], desc="Order Basket Weight"
        )
        order_management.reporter.write_body(data=deposit_info, desc="Deposit ratio")
        order_management.reporter.write_body(
            data=summary[non_weight_columns], desc="Order Basket Detail"
        )
        order_management.reporter.save()


class OrderAccountFetcher(Task, PortfolioMapMixin):
    def __init__(self, *args, **kwargs):
        super(OrderAccountFetcher, self).__init__(*args, **kwargs)
        self.portfolio_map = dict()
        self.exchange_rate = None

    def process(self, vendor_code, *args, **kwargs):
        if not vendor_code:
            logger.warning("vendor_code is must be passed")
            return

        CachedTickerStager.flush_all()
        us_date_as_kst = get_us_today_as_kst()
        kst_today = get_local_today()

        self.portfolio_map = self.get_portfolio_map(
            filter_date=kst_today.strftime("%Y-%m-%d")
        )

        self.exchange_rate = ForeignCurrency.get_exchange_rate(
            api_base=TR_BACKEND[str(vendor_code).upper()].HOST
        )

        logger.info("RUN Order Account Selection")
        self.cancel_delayed_queues(base_datetime=us_date_as_kst, vendor_code=vendor_code)

        self.update_event(vendor_code=vendor_code, base_date=kst_today.date())
        order_account_queryset = self.get_order_account_queryset(
            vendor_code=vendor_code, base_date=kst_today.date()
        )
        self.register_sell_order_queues(
            vendor_code=vendor_code, base_date=kst_today.date()
        )
        self.register_normal_order_queues(
            queryset=order_account_queryset, vendor_code=vendor_code
        )

    def update_event(self, vendor_code, base_date):
        queryset = self.get_order_account_queryset(
            vendor_code=vendor_code, base_date=base_date
        )
        latest_event_by_account = Event.objects.filter(
            id__in=(
                Event.objects.filter(account_alias__vendor_code=vendor_code).values("account_alias_id")
                .annotate(Max("id"))
                .order_by("account_alias_id")
                .values_list("id__max", flat=True)
            )
        )
        update_needed_events = []
        new_needed_events = []
        for (
            _account_alias,
            _risk_type,
            _strategy_code,
            _order_event_status,
            _order_mode,
        ) in queryset.iterator():
            account = Account.objects.get(account_alias=_account_alias)
            strategy = str(int(_strategy_code)).zfill(2)
            port_seq = self.portfolio_map[strategy][str(_risk_type)]["port_seq"]
            event_row = latest_event_by_account.filter(
                account_alias_id=_account_alias
            ).first()
            if (event_row.mode == Event.MODES.new_order) & (
                event_row.portfolio_id != port_seq
            ):
                if event_row.status in [Event.STATUS.on_hold, Event.STATUS.processing]:
                    event_row.portfolio_id = port_seq
                    update_needed_events.append(event_row)

                elif event_row.status in [Event.STATUS.completed]:
                    new_event = Event(
                        account_alias=account,
                        mode=Event.MODES.rebalancing,
                        portfolio_id=port_seq,
                    )
                    new_needed_events.append(new_event)
                else:
                    pass

            elif (event_row.mode == Event.MODES.rebalancing) & (
                event_row.portfolio_id != port_seq
            ):
                if event_row.status == Event.STATUS.on_hold:
                    event_row.portfolio_id = port_seq
                    update_needed_events.append(event_row)

                elif event_row.status == Event.STATUS.processing:
                    event_row.status = Event.STATUS.canceled
                    update_needed_events.append(event_row)
                    new_event = Event(
                        account_alias=account,
                        mode=Event.MODES.rebalancing,
                        portfolio_id=port_seq,
                    )
                    new_needed_events.append(new_event)

                elif event_row.status in [Event.STATUS.completed]:
                    new_event = Event(
                        account_alias=account,
                        mode=Event.MODES.rebalancing,
                        portfolio_id=port_seq,
                    )
                    new_needed_events.append(new_event)
                else:
                    pass
            else:
                pass

        Event.objects.bulk_update(update_needed_events, ["status", "portfolio_id"])
        Event.objects.bulk_create(new_needed_events)

    def register_normal_order_queues(self, queryset, vendor_code):
        exchange_rate = ForeignCurrency.get_exchange_rate(
            api_base=TR_BACKEND[str(vendor_code).upper()].HOST
        )

        # 정상계약 주문 등록 (최근의 Order.Event의 status 기반으로 판단)
        for (
            _account_alias,
            _risk_type,
            _strategy_code,
            _order_event_status,
            _order_mode,
        ) in queryset.iterator():
            # 계좌의 최신 요청 주문의 status가 대기, 진행, 완료인 상태인 경우만, OrderQueue(management.order_router)에 등록
            if _order_event_status in [
                Event.STATUS.on_hold,
                Event.STATUS.processing,
                Event.STATUS.completed,
            ]:
                daily_order_mode = _order_mode

                # 최신 요청 주문이 완료된 경우에는 리밸런싱 모드로 운영
                if _order_event_status == Event.STATUS.completed:
                    daily_order_mode = Event.MODES.rebalancing
                strategy = str(int(_strategy_code)).zfill(2)
                portfolio = self.portfolio_map[strategy].get(str(_risk_type))
                self.register_queue_with_basket.apply_async(
                    [
                        _account_alias,
                        portfolio,
                        daily_order_mode,
                        exchange_rate,
                        vendor_code,
                    ]
                )

    @staticmethod
    @shared_task(bind=True, base=OrderQueueRegisterRunner)
    def register_queue_with_basket(
        runner: OrderQueueRegisterRunner,
        account_alias,
        portfolio,
        daily_order_mode,
        exchange_rate,
        vendor_code,
        *args,
        **kwargs,
    ):
        return runner.process(
            account_alias=account_alias,
            portfolio=portfolio,
            exchange_rate=exchange_rate,
            daily_order_mode=daily_order_mode,
            vendor_code=vendor_code,
            *args,
            **kwargs,
        )

    @staticmethod
    def cancel_delayed_queues(base_datetime: datetime, vendor_code):
        # 처리일 이전에 대기중 혹은 진행중으로 남은 주문들은 실패 처리함
        neglected_order_queryset = Queue.objects.filter(
            created__lt=base_datetime,
            status__in=[Queue.STATUS.on_hold, Queue.STATUS.processing],
            vendor_code=vendor_code,
        )

        if neglected_order_queryset.exists():
            logger.warning(
                f"neglected orders({neglected_order_queryset.count()}): "
                f"{neglected_order_queryset.values('id', 'status', 'account_alias')}"
            )
            neglected_order_queryset.update(status=Queue.STATUS.canceled)

    @staticmethod
    def get_order_account_queryset(vendor_code, base_date: datetime):
        # 당일 주문 처리된 계좌 선정 제외
        accounts_having_been_ordered = Queue.objects.filter(
            management_at__date=base_date
        ).values_list("account_alias", flat=True)
        logger.info(f"Already registered Queue: {accounts_having_been_ordered.count()}")

        # 당일 주문 처리가 완료되지 않은 계좌 선정
        account_having_order_queryset = (
            Account.objects.annotate(latest_event_date=Max("event__created_at"))
            .filter(
                risk_type__isnull=False,
                event__isnull=False,
                event__created_at=F("latest_event_date"),
                status=Account.STATUS.normal,
                vendor_code=vendor_code,
            )
            .exclude(account_alias__in=set(accounts_having_been_ordered))
        )
        logger.info(
            f"Total normal OrderAccount: {account_having_order_queryset.count()}"
        )

        order_account_queryset = account_having_order_queryset.values_list(
            "account_alias",
            "risk_type",
            "strategy_code",
            "event__status",
            "event__mode",
        )

        return order_account_queryset

    def register_sell_order_queues(self, vendor_code, base_date):
        # 해지 매도 대상 계좌 선정 (Account 상태로 판단)
        accounts_having_sell_order = Queue.objects.filter(
            management_at__date=base_date, mode=Queue.MODES.sell,
            vendor_code=vendor_code
        ).values_list("account_alias", flat=True)
        account_being_closed_queryset = Account.objects.filter(
            risk_type__isnull=False,
            status__in=[Account.STATUS.account_sell_reg],
            vendor_code=vendor_code,
        ).exclude(account_alias__in=set(accounts_having_sell_order))

        logger.info(
            f"try register sell_order_queues: {account_being_closed_queryset.count()}"
        )
        # 해지 대기 계약 주문 bulk
        queues = []
        for _account in account_being_closed_queryset.iterator():
            strategy = str(int(_account.strategy_code)).zfill(2)
            port_data = self.portfolio_map[strategy].get(str(_account.risk_type))[
                "port_data"
            ]
            port_seq = self.portfolio_map[strategy].get(str(_account.risk_type))[
                "port_seq"
            ]
            om, order_basket = None, None
            note = ""

            try:
                om = OrderManagement(
                    account_alias=_account.account_alias,
                    data_stager=CachedTickerStager(api_url=INFOMAX_BACKEND.API_HOST),
                    portfolio=port_data,
                    exchange_rate=self.exchange_rate,
                    vendor_code=vendor_code,
                    mode=Event.MODES.sell,
                )
                order_basket = om.order_basket

            except UnsupportedTicker as e:
                note = f"운용 중지(미지원 종목 포함): {str(e)}"
                stop_account_operation(account_alias=_account)

            except Exception as e:
                note = f"{str(e)}"

            _order_queue = Queue(
                account_alias=_account.account_alias,
                portfolio_id=port_seq,
                mode=Queue.MODES.sell,
                status=Queue.STATUS.pending,
                vendor_code=vendor_code,
            )

            _order_queue.set_order_basket(order_basket=order_basket, note=note)
            update_account_being_closed_status(queue=_order_queue)
            queues.append(_order_queue)

        bulked = Queue.objects.bulk_create(queues)
        logger.info(f"sell_order_queues have been registered: {len(bulked)}")


class ExecutionManagementRunner(Task):
    def process(
        self,
        order_queue_id,
        portfolio,
        exchange_rate,
        vendor_code,
        order_type_to_plan,
        *args,
        **kwargs,
    ):
        infomax_api_base = INFOMAX_BACKEND.API_HOST
        desc, msg = "", ""
        report_type = OrderReport.REPORT_TYPES.monitoring
        order_queue = Queue.objects.get(id=order_queue_id)

        em = None
        try:
            em = ExecutionManagement(
                account_alias=order_queue.account_alias,
                order_queue_id=order_queue_id,
                exchange_rate=exchange_rate,
                data_stager=CachedTickerStager(api_url=infomax_api_base),
                min_deposit_ratio=0.05,
                vendor_code=vendor_code,
            )
            if em.unexecuted_trd_history.empty and order_type_to_plan["order_type"] in [
                "Adjust",
                "Cancel",
            ]:
                OrderLog.objects.complete_executed_orders(
                    order_queue_id=order_queue_id, unexecuted_codes=[]
                )
                self.update_order_account_status(execution_management=em)
                return
            if em.order_position == LONG_POSITION:
                canceled_order_logs = em.cancel_orders(position=SHORT_POSITION)
            else:
                canceled_order_logs = em.cancel_orders(position=LONG_POSITION)
            em.reporter.write_body(data=em.current_portfolio, desc="현재 포트폴리오")
            em.route_orders(order_type_to_plan)
            self.update_order_account_status(execution_management=em)
            em.save_report()

        except StopOrderOperation as e:
            stop_account_operation(account_alias=order_queue.account_alias)
            desc, msg = f"운용 중지({str(order_queue.account_alias)})", f"{str(e)}"
            report_type = OrderReport.REPORT_TYPES.anomaly
            logger.error(msg)

        except PreconditionFailed as e:
            desc, msg = f"사전 조건 실패", f"{str(e)}"
            report_type = OrderReport.REPORT_TYPES.error
            logger.error(msg)

        except UnsupportedTicker as e:
            stop_account_operation(account_alias=order_queue.account_alias)
            desc, msg = f"운용 중지(미지원 종목 포함)", f"{str(e)}"
            report_type = OrderReport.REPORT_TYPES.error
            logger.error(msg)

        except Exception as e:
            desc, msg = f"unexpected error", f"{str(e)}"
            report_type = OrderReport.REPORT_TYPES.error
            logger.error(msg)
        finally:
            if report_type in [
                OrderReport.REPORT_TYPES.anomaly,
                OrderReport.REPORT_TYPES.error,
            ]:
                queue_context = QueueStatusContext(order_queue=order_queue)
                queue_context.transition(status=Queue.STATUS.failed)

                order_report, is_created = OrderReport.objects.get_or_create(
                    order=order_queue
                )
                order_report.write_body(data=msg, desc=desc)
                order_report.report_type = report_type
                logger.info(f"Fail processing orders: {order_queue}")

    @staticmethod
    def update_order_account_status(execution_management: ExecutionManagement):
        # 정상 계약 주문 처리 상태 업데이트
        queryset = Event.objects.filter(
            account_alias=execution_management.order_queue.account_alias
        ).order_by("-created_at")
        base_datetime = get_us_today_as_kst()

        if queryset.exists():
            if execution_management.order_queue.account.status == Account.STATUS.normal:
                target_queues = Queue.objects.filter(
                    account_alias=execution_management.order_queue.account_alias,
                    management_at__date=base_datetime.date(),
                )
                remaining_queues = target_queues.filter(
                    status__in=[
                        Queue.STATUS.on_hold,
                        Queue.STATUS.pending,
                        Queue.STATUS.processing,
                    ]
                )
                completed_order_logs = OrderLog.objects.filter(
                    order__in=target_queues.values_list("id", flat=True),
                    status=OrderLog.STATUS.completed,
                )

                latest_order_event = queryset.first()
                if remaining_queues.exists():
                    latest_order_event.process()  # Event.on_hold -> Event.processing
                elif completed_order_logs.exists():
                    # 처리 중인 큐가 없고, 성공한 주문이 하나라도 있는 경우 Event(신규, 리밸런싱)는 성공으로 처리
                    latest_order_event.complete()  # Event.processing -> Event.completed

            elif execution_management.order_queue.is_account_being_closed:
                update_account_being_closed_status(
                    queue=execution_management.order_queue
                )


class ExecutionManagementRegister(Task, PortfolioMapMixin):
    def __init__(self, *args, **kwargs):
        super(ExecutionManagementRegister, self).__init__(*args, **kwargs)
        self.portfolio_map = dict()

    def get_queryset(self, position):
        default_queryset = Queue.objects.filter(
            status__in=[Queue.STATUS.on_hold, Queue.STATUS.processing]
        )
        position_queryset_map = {
            "S": self.get_short_order_queues(),
            "L": self.get_long_order_queues(),
        }
        return position_queryset_map.get(position, default_queryset)

    def cancel_unexecuted_orders(self, vendor_code, position=None):
        base_date = get_us_today_as_kst()
        data_stager = CachedTickerStager(api_url=INFOMAX_BACKEND.API_HOST)
        exchange_rate = ForeignCurrency.get_exchange_rate(
            api_base=TR_BACKEND[str(vendor_code).upper()].HOST
        )
        queryset = self.get_queryset(position=position)

        for _queue in queryset.iterator():
            try:
                em = ExecutionManagement(
                    account_alias=_queue.account_alias,
                    order_queue_id=_queue,
                    exchange_rate=exchange_rate,
                    data_stager=data_stager,
                    vendor_code=vendor_code,
                )

                canceled_order_logs = em.cancel_orders(position=position)

                if canceled_order_logs:
                    # 체결된 종목에 대해서는 완료 처리함
                    OrderLog.objects.filter(
                        order=_queue, status=OrderLog.STATUS.processing
                    ).exclude(code__in=[c.code for c in canceled_order_logs]).update(
                        status=OrderLog.STATUS.completed
                    )
                    em.status_context.transition(status=Queue.STATUS.canceled)

                elif em.is_remaining_order_basket_empty:
                    em.status_context.transition(status=Queue.STATUS.completed)
                ExecutionManagementRunner.update_order_account_status(
                    execution_management=em
                )

            except Exception as e:
                reporter = OrderReporter(
                    queue=_queue,
                    vendor_code=vendor_code,
                    account_number=_queue.account.account_number,
                    report_type=OrderReport.REPORT_TYPES.error,
                )

                reporter.update_title(title="주문 처리 실패 오류")
                reporter.write_body(data=str(e), desc="ErrorMessage")
                reporter.save()

                _queue.note = f"주문취소 실패:{str(e)[:MAX_NOTE_SIZE]}"
                queue_context = QueueStatusContext(order_queue=_queue)
                queue_context.transition(status=Queue.STATUS.canceled)

    def cancel_twap_orders(
        self,
        vendor_code,
        _queue_id,
        exchange_rate,
        data_stager,
        order_type_to_plan=None,
    ):
        position = order_type_to_plan["position"]
        _remaining_number_of_order = order_type_to_plan["remaining_number_of_order"]
        order_queue = Queue.objects.get(id=_queue_id)
        try:
            em = ExecutionManagement(
                account_alias=order_queue.account_alias,
                order_queue_id=_queue_id,
                exchange_rate=exchange_rate,
                data_stager=data_stager,
                vendor_code=vendor_code,
            )
            canceled_order_logs = em.cancel_orders(position=position)

            if canceled_order_logs:
                # 체결된 종목에 대해서는 완료 처리함
                OrderLog.objects.filter(
                    order=order_queue, status=OrderLog.STATUS.processing
                ).exclude(code__in=[c.code for c in canceled_order_logs]).update(
                    status=OrderLog.STATUS.completed
                )
                # 취소된 종목에 대해서는 캔슬 처리함
                OrderLog.objects.filter(
                    order=order_queue,
                    status=OrderLog.STATUS.processing,
                    code__in=[c.code for c in canceled_order_logs],
                ).update(status=OrderLog.STATUS.canceled)

                logger.debug(
                    f"--before basket_empty_check-- |"
                    f"em.account_number: {em.account_number} | "
                    f"order_queue_status: {order_queue.status} | "
                    f"em.is_remaining_order_basket_empty: {em.remaining_order_basket['shares'].to_dict()} | "
                    f"current_portfolio: {em.current_portfolio['shares'].to_dict()} | "
                    f"shares: {em._proxy.shares.set_index('code')['shares'].to_dict()} |"
                )

            else:
                OrderLog.objects.filter(
                    order=order_queue, status=OrderLog.STATUS.processing
                ).update(status=OrderLog.STATUS.completed)

            # Apply cancel order to account
            em._proxy.reset_current_portfolio_cache()
            em._proxy.set_assets()

            # 목표 주문 완료 여부 확인.
            if em.is_remaining_order_basket_empty and not canceled_order_logs:
                em.status_context.transition(status=Queue.STATUS.completed)
                logger.debug(
                    f"--after basket_empty_check-- |"
                    f"em.account_number: {em.account_number} | "
                    f"order_queue_status: {order_queue.status} | "
                    f"em.is_remaining_order_basket_empty: { em.remaining_order_basket['shares'].to_dict()} | "
                    f"current_portfolio: {em.current_portfolio['shares'].to_dict()} | "
                    f"shares: {em._proxy.shares.set_index('code')['shares'].to_dict()} |"
                )

            elif _remaining_number_of_order == 0:
                em.status_context.transition(status=Queue.STATUS.canceled)

            ExecutionManagementRunner.update_order_account_status(
                execution_management=em
            )

        except Exception as e:
            reporter = OrderReporter(
                queue=order_queue,
                vendor_code=vendor_code,
                account_number=order_queue.account.account_number,
                report_type=OrderReport.REPORT_TYPES.error,
            )

            reporter.update_title(title="주문 처리 실패 오류")
            reporter.write_body(data=str(e), desc="ErrorMessage")
            reporter.save()

            # 주문 취소는 실패할 수 있음.
            if _remaining_number_of_order == 0:
                order_queue.note = f"주문취소 실패:{str(e)[:MAX_NOTE_SIZE]}"
                queue_context = QueueStatusContext(order_queue=order_queue)
                queue_context.transition(status=Queue.STATUS.canceled)

    def process(self, position, vendor_code, sub_task_expires, *args, **kwargs):
        if not vendor_code:
            logger.warning("vendor code must be passed")
            return
        if position not in [SHORT_POSITION, LONG_POSITION]:
            logger.warning(f"invalid position({position})")
            return

        # 1. 기존 주문 처리에 사용하던 가격 캐시 초기화
        CachedTickerStager.flush_all()
        us_today = get_us_today_as_kst()
        self.portfolio_map = self.get_portfolio_map(
            filter_date=us_today.strftime("%Y-%m-%d")
        )
        self.exchange_rate = ForeignCurrency.get_exchange_rate(
            api_base=TR_BACKEND[str(vendor_code).upper()].HOST
        )

        if position == SHORT_POSITION:
            order_queues = self.get_short_order_queues()
        elif position == LONG_POSITION:
            order_queues = self.get_long_order_queues()
        else:
            raise TypeError(f"Unsupported position")

        # 2. 매도 주문 우선 처리
        if order_queues.exists():
            self.execute_orders(
                order_queues=order_queues,
                exchange_rate=self.exchange_rate,
                vendor_code=vendor_code,
                sub_task_expires=int(sub_task_expires),
            )
        else:
            logger.info("order queues empty")

    def get_short_order_queues(self):
        return Queue.objects.filter(
            mode__in=[Queue.MODES.sell, Queue.MODES.ask],
            status__in=[Queue.STATUS.on_hold, Queue.STATUS.processing],
        )

    def get_long_order_queues(self):
        return Queue.objects.filter(
            mode__in=[Queue.MODES.bid],
            status__in=[Queue.STATUS.on_hold, Queue.STATUS.processing],
        )

    def execute_orders(
        self, order_queues, exchange_rate, vendor_code, sub_task_expires=1
    ):
        results = []
        for _queue in order_queues.iterator():
            strategy = str(_queue.portfolio_id)[-5:-3]
            risk_type = str(_queue.portfolio_id)[-3]
            port = self.portfolio_map[strategy].get(str(risk_type))["port_data"]
            res = self.run_execution_management.apply_async(
                [_queue.id, port, exchange_rate, vendor_code],
                retry=False,
                expires=sub_task_expires,
            )
            results.append(res)
        return results

    @staticmethod
    @shared_task(bind=True, base=ExecutionManagementRunner)
    def run_execution_management(
        runner: ExecutionManagementRunner,
        order_queue_id,
        portfolio,
        exchange_rate,
        vendor_code,
        *args,
        **kwargs,
    ):
        return runner.process(
            order_queue_id=order_queue_id,
            portfolio=portfolio,
            exchange_rate=exchange_rate,
            vendor_code=vendor_code,
            *args,
            **kwargs,
        )


class ErrorAccountMonitor(Task, PortfolioMapMixin):
    def process(self, monitor_dates, *args, **kwargs):
        monitor_dates = (
            monitor_dates
            if monitor_dates is not None
            else [(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")]
        )
        exclude_notes = ["리밸런싱 조건에 미해당", "해당 국가 휴일로 주문 불가능합니다."]

        for s_date in monitor_dates:
            s_date_utc = datetime.strptime(s_date, "%Y-%m-%d")
            # 01. 날짜에 해당하는 Queue, 로그, 리포트  찾기.
            daily_account = Account.objects.filter(
                updated_at__gte=s_date_utc,
                updated_at__lte=s_date_utc + timedelta(days=1),
            )
            daily_queue = Queue.objects.filter(created__startswith=s_date)
            daily_orderlog = OrderLog.objects.filter(
                created__startswith=s_date
            ).exclude(error_msg__in=exclude_notes)
            if len(daily_orderlog) == 0:
                continue

            # 02. 에러 계좌 현황
            error_solved_queryset = ErrorOccur.objects.filter(
                Q(errorsolved__solved_at__isnull=False)
            )
            error_live_queryset = ErrorOccur.objects.filter(
                Q(errorsolved__solved_at__isnull=True), Q(occured_at__lte=s_date_utc)
            )
            error_live_accnts = error_live_queryset.values_list(
                "account_alias", flat=True
            ).distinct()

            # 03. 오늘자 에러 계좌 찾기.
            type_to_error_account_alias = self.get_type_to_error_account_alias(
                s_date, exclude_notes, daily_orderlog, daily_queue, daily_account
            )

            # 04. 에러 해결된 계좌 업데이트.
            daily_queue_excluded = daily_queue.exclude(note__in=exclude_notes)
            solved_ids = self.get_error_solved_accnts(
                error_live_queryset,
                daily_queue_excluded,
                daily_account,
                type_to_error_account_alias,
                s_date_utc,
            )
            solved_errors = []
            for sovled_id in solved_ids:
                solve_error_object = ErrorSolved(
                    error_occur_id=sovled_id,
                    solved_at=s_date,
                )
                solved_errors.append(solve_error_object)
            ErrorSolved.objects.bulk_create(solved_errors)

            # 05. 신규 에러 계좌 업데이트.
            new_errors = []
            for error_id in type_to_error_account_alias:
                error_accnts = list(type_to_error_account_alias[error_id].keys())

                already_error_solved_accnts = (
                    error_solved_queryset.filter(
                        occured_at__lte=s_date_utc,
                        errorsolved__solved_at__gte=s_date_utc,
                        error_id=error_id,
                    )
                    .values_list("account_alias", flat=True)
                    .distinct()
                )

                already_error_live_accnts = (
                    error_live_queryset.filter(error_id=error_id)
                    .values_list("account_alias", flat=True)
                    .distinct()
                )

                new_error_accounts = list(
                    set(error_accnts)
                    - set(already_error_live_accnts)
                    - set(already_error_solved_accnts)
                )
                for account_alias in new_error_accounts:
                    new_error_object = ErrorOccur(
                        error_id=error_id,
                        order_id=type_to_error_account_alias[error_id][account_alias],
                        account_alias=account_alias,
                        occured_at=s_date,
                    )
                    new_errors.append(new_error_object)

            ErrorOccur.objects.bulk_create(new_errors)
        self.check_sell_fail_account()

    def get_error_solved_accnts(
        self,
        error_live_queryset,
        daily_queue_excluded,
        daily_account,
        type_to_error_account_alias,
        s_date_utc,
    ):
        error_live_accnts = error_live_queryset.values_list(
            "account_alias", flat=True
        ).distinct()
        canceled_accnts = daily_account.filter(status=0).values_list(
            "account_alias", flat=True
        )

        queue_order_ok = daily_queue_excluded.filter(note__isnull=True).exclude(
            account_alias__in=list(type_to_error_account_alias[1005].keys())
        )
        queue_order_ok_accnts = list(
            queue_order_ok.values_list("account_alias", flat=True)
        )

        solved_accnts = list(
            (set(error_live_accnts) & set(queue_order_ok_accnts)) | set(canceled_accnts)
        )
        solved_ids = error_live_queryset.filter(
            account_alias__in=solved_accnts
        ).values_list("error_occur_id", flat=True)
        return solved_ids

    def get_type_to_error_account_alias(
        self, s_date, exclude_notes, daily_orderlog, daily_queue, daily_account
    ):

        daily_queue_excluded = daily_queue.exclude(note__in=exclude_notes)
        type_to_error_account_alias = {}
        portfolio_map = self.get_portfolio_map(filter_date=s_date)
        data_stager = CachedTickerStager(api_url=INFOMAX_BACKEND.API_HOST)
        port_seq_to_mp_tickers = {}
        wgt_error_port_seqs = []
        for strategy_code in portfolio_map.keys():
            for risk in portfolio_map[strategy_code].keys():
                port_seq = portfolio_map[strategy_code][risk]["port_seq"]
                df_port_data = pd.DataFrame(
                    portfolio_map[strategy_code][risk]["port_data"]
                )
                port_seq_to_mp_tickers[port_seq] = df_port_data.code.to_list()
                if df_port_data["weight"].sum().round(6) != 1:
                    wgt_error_port_seqs.append(port_seq)

        port_seq_to_error_tickers = {}
        for port_seq in port_seq_to_mp_tickers.keys():
            port_seq_to_error_tickers[port_seq] = []
            mps = port_seq_to_mp_tickers[port_seq]
            for ticker in mps:
                try:
                    data_stager.get_prices([ticker])
                except:
                    port_seq_to_error_tickers[port_seq].append(ticker)

        px_error_port_seqs = [
            port_seq
            for port_seq in port_seq_to_error_tickers
            if len(port_seq_to_error_tickers[port_seq]) > 0
        ]

        type_to_error_account_alias[2001] = dict(
            daily_queue.filter(portfolio_id__in=wgt_error_port_seqs)
            .values("account_alias")
            .annotate(max_id=Max("id"))
            .values_list("account_alias", "max_id")
        )

        type_to_error_account_alias[2002] = dict(
            daily_queue.filter(portfolio_id__in=px_error_port_seqs)
            .values("account_alias")
            .annotate(max_id=Max("id"))
            .values_list("account_alias", "max_id")
        )

        error_code_to_error_str = {
            1001: "must be larger than min_base",
            1002: "are unavailable assets",
            1003: "Has invalid transaction history",
            2004: "url:",
            2005: "emphasis",
            2006: "Unsupported portfolio type",
        }

        for error_code, error_str in error_code_to_error_str.items():
            type_to_error_account_alias[error_code] = dict(
                daily_queue_excluded.filter(note__contains=error_str)
                .values("account_alias")
                .annotate(max_id=Max("id"))
                .values_list("account_alias", "max_id")
            )

        # 해지매도 실패
        type_to_error_account_alias[1004] = list(
            daily_account.filter(status=23)
            .values_list("account_alias", flat=True)
            .distinct()
        )
        type_to_error_account_alias[1004] = {
            accnt: None for accnt in type_to_error_account_alias[1004]
        }
        # 비밀번호 사고 계좌
        type_to_error_account_alias[1005] = daily_orderlog.filter(
            error_msg__isnull=False, error_msg__contains="사고"
        )
        type_to_error_account_alias[1005] = list(
            type_to_error_account_alias[1005]
            .values_list("order__account_alias", flat=True)
            .distinct()
        )
        type_to_error_account_alias[1005] = {
            accnt: None for accnt in type_to_error_account_alias[1005]
        }

        return type_to_error_account_alias

    def check_sell_fail_account(self):
        # 시장상황 때문에 해지매도 실패 한 경우, 계좌 상태값 해지매도 진행 중으로 원상복구
        account_sell_failed = Account.objects.filter(
            risk_type__isnull=False,
            status__in=[Account.STATUS.account_sell_f1],
        ).values_list("account_alias", flat=True)
        for account_alias in account_sell_failed:
            manual_needed_error_history = ErrorOccur.objects.filter(
                error_id__in=[1001, 1002, 1003], account_alias__in=[account_alias]
            )
            closed_manual_needed_error_history = manual_needed_error_history.filter(
                errorsolved__solved_at__isnull=False
            )
            if len(manual_needed_error_history) == len(
                closed_manual_needed_error_history
            ):
                account_object = Account.objects.filter(account_alias=account_alias)
                account_object.update(status=Account.STATUS.account_sell_reg)


class SplitOrderController(Task, PortfolioMapMixin):
    def __init__(self, *args, **kwargs):
        pass

    def executer(self, vendor_code, time_schedule, min_qty, sub_task_expires):
        us_datetime = get_us_today()
        order_type_to_plan = self.get_order_type_to_plan(
            us_datetime, time_schedule, min_qty
        )
        if order_type_to_plan is None:
            return
        self.order_queues = self.get_order_queues(
            vendor_code, us_datetime.date(), order_type_to_plan["position"]
        )

        portfolio_map = self.get_portfolio_map(
            filter_date=us_datetime.date().strftime("%Y-%m-%d")
        )
        exchange_rate = ForeignCurrency.get_exchange_rate(
            api_base=TR_BACKEND[str(vendor_code).upper()].HOST
        )
        if order_type_to_plan["order_type"] in ["Cancel"]:
            self.execute_cancel(
                self.order_queues,
                vendor_code,
                order_type_to_plan,
                sub_task_expires=sub_task_expires,
            )
        else:
            self.execute_twap(
                self.order_queues,
                portfolio_map,
                exchange_rate,
                vendor_code,
                order_type_to_plan,
                sub_task_expires=sub_task_expires,
            )

    def get_order_type_to_plan(self, us_datetime, time_schedule, min_qty):
        order_type_to_plan = {}
        now_strftime = us_datetime.strftime("%H:%M")
        now_adjust = now_strftime[:-1] + "0"

        df_schedule = pd.DataFrame(TIME_SCHEDULE[time_schedule])
        n_row, n_col = df_schedule.shape

        find_idx = df_schedule.values.flatten() >= now_adjust
        if any(find_idx):
            idx = min(np.where(find_idx)[0])
        else:
            return

        position, order_type = df_schedule.columns[idx % n_col].split("_")
        order_type_to_plan["min_qty"] = int(min_qty)
        order_type_to_plan["now_strftime"] = now_strftime
        order_type_to_plan["now_adjust"] = now_adjust
        order_type_to_plan["position"] = position[0]
        order_type_to_plan["order_type"] = order_type
        order_type_to_plan["current_number_of_order"] = int(
            df_schedule.index[idx // n_col]
        )
        order_type_to_plan["total_number_of_order"] = int(n_row)
        order_type_to_plan["remaining_number_of_order"] = int(
            n_row - order_type_to_plan["current_number_of_order"]
        )
        return order_type_to_plan

    def get_order_queues(self, vendor_code, search_date, position):
        if position.upper() == "S":
            cancel_accounts = Account.objects.filter(
                risk_type__isnull=False,
                status__in=[Account.STATUS.account_sell_reg],
                vendor_code=vendor_code,
            ).values_list("account_alias", flat=True)

            total_queue_set = Queue.objects.filter(
                created__startswith=search_date,
                mode__in=[Queue.MODES.sell, Queue.MODES.ask],
                status__in=[Queue.STATUS.on_hold, Queue.STATUS.processing],
            )

            ordered_queue_set = total_queue_set.annotate(
                is_cancel_account=Case(
                    When(account_alias__in=list(cancel_accounts), then=Value(True)),
                    default=False,
                    output_field=BooleanField(),
                )
            ).order_by("-is_cancel_account")

            return ordered_queue_set

        if position.upper() == "L":
            new_order_accounts = (
                Account.objects.annotate(latest_event_date=Max("event__created_at"))
                .filter(
                    event__created_at=F("latest_event_date"),
                    event__mode="new_order",
                    vendor_code=vendor_code,
                )
                .values_list("account_alias", flat=True)
            )

            total_queue_set = Queue.objects.filter(
                created__startswith=search_date,
                mode__in=[Queue.MODES.bid],
                status__in=[Queue.STATUS.on_hold, Queue.STATUS.processing],
            )

            ordered_queue_set = total_queue_set.annotate(
                is_new_account=Case(
                    When(account_alias__in=list(new_order_accounts), then=Value(True)),
                    default=False,
                    output_field=BooleanField(),
                )
            ).order_by("-is_new_account")

            return ordered_queue_set

    def execute_twap(
        self,
        order_queues,
        portfolio_map,
        exchange_rate,
        vendor_code,
        order_type_to_plan,
        sub_task_expires=1,
    ):
        results = []
        for _queue in order_queues.iterator():
            strategy = str(_queue.portfolio_id)[-5:-3]
            risk_type = str(_queue.portfolio_id)[-3]
            port = portfolio_map[strategy].get(str(risk_type))["port_data"]
            res = self.run_split_execution.apply_async(
                [_queue.id, port, exchange_rate, vendor_code, order_type_to_plan],
                retry=False,
                expires=sub_task_expires,
            )
            results.append(res)
        return results

    def execute_cancel(
        self, order_queues, vendor_code, order_type_to_plan, sub_task_expires=1
    ):
        exchange_rate = ForeignCurrency.get_exchange_rate(
            api_base=TR_BACKEND[str(vendor_code).upper()].HOST
        )
        results = []
        for _queue in order_queues.iterator():
            res = self.run_split_cancel.apply_async(
                [vendor_code, _queue.id, exchange_rate, order_type_to_plan],
                retry=False,
                expires=sub_task_expires,
            )
            results.append(res)
        return results

    @staticmethod
    @shared_task(bind=True, base=ExecutionManagementRunner)
    def run_split_execution(
        runner: ExecutionManagementRunner,
        order_queue_id,
        portfolio,
        exchange_rate,
        vendor_code,
        order_type_to_plan,
        *args,
        **kwargs,
    ):
        return runner.process(
            order_queue_id=order_queue_id,
            portfolio=portfolio,
            exchange_rate=exchange_rate,
            vendor_code=vendor_code,
            order_type_to_plan=order_type_to_plan,
            *args,
            **kwargs,
        )

    @staticmethod
    @shared_task(bind=True, base=ExecutionManagementRegister)
    def run_split_cancel(
        runner: ExecutionManagementRegister,
        vendor_code,
        _queue_id,
        exchange_rate,
        order_type_to_plan,
        *args,
        **kwargs,
    ):
        data_stager = CachedTickerStager(api_url=INFOMAX_BACKEND.API_HOST)
        return runner.cancel_twap_orders(
            vendor_code,
            _queue_id,
            exchange_rate,
            data_stager,
            order_type_to_plan=order_type_to_plan,
            *args,
            **kwargs,
        )


# 환전
class AbstractCurrencyExchangerRunner(ABC, Task):
    """환전 실행 - 개별 계좌"""

    exchanger = AbstractCurrencyExchanger

    def process(self, account_alias: str, *args, **kwargs) -> dict:
        account = self._get_account_by_account_alias(account_alias)
        result = self.exchanger(account).process()
        return result.data

    @staticmethod
    def _get_account_by_account_alias(account_alias: str) -> Account:
        return Account.objects.get(account_alias=account_alias)


class CurrencyExchangerRunnerForAccountBeingClosed(AbstractCurrencyExchangerRunner):
    """환전 실행 - 개별 계좌(해지 매도 계좌)"""

    exchanger = CurrencyExchangerForAccountBeingClosed


class CurrencyExchangerRunnerForAccountNormal(AbstractCurrencyExchangerRunner):
    """환전 실행 - 개별 계좌(정상 계좌)"""

    exchanger = CurrencyExchangerForAccountNormal


@dataclass
class CurrencyExchangerRunnerForAllAccountsWithVendorResult:
    account_aliases: list[str]

    @property
    def data(self):
        return dict(
            count=len(self.account_aliases), account_aliases=self.account_aliases
        )


class AbstractCurrencyExchangerRunnerForAllAccountsWithVendor(ABC, Task):
    """환전 실행 - 특정 증권사 전체 계좌"""

    @abstractproperty
    def get_accounts(self):
        pass

    @abstractproperty
    def exchange(self):
        # Call celery task to exchange here.
        pass

    def process(self, vendor_code: str, *args, **kwargs) -> dict:
        account_aliases = get_account_aliases_from_accounts_with_test_account_aliases(
            self.get_accounts(vendor_code), kwargs.get("test_account_aliases")
        )
        if not kwargs.get("is_dry_run", False):
            self._process_all_account_aliases(account_aliases)
        return CurrencyExchangerRunnerForAllAccountsWithVendorResult(
            account_aliases
        ).data

    def _process_all_account_aliases(self, account_aliases: list[str]) -> None:
        for account_alias in account_aliases:
            self.exchange.apply_async((account_alias,))


class CurrencyExchangerRunnerForAllAccountsBeingClosedWithVendor(
    AbstractCurrencyExchangerRunnerForAllAccountsWithVendor
):
    """환전 실행 - 특정 증권사 전체 계좌(해지 매도 계좌)"""

    @property
    def get_accounts(self):
        return get_accounts_being_closed_etf

    @property
    def exchange(self):
        return exchange_account_being_closed


class CurrencyExchangerRunnerForAllAccountsNormalWithVendor(
    AbstractCurrencyExchangerRunnerForAllAccountsWithVendor
):
    """환전 실행 - 특정 증권사 전체 계좌(정상 계좌)"""

    @property
    def get_accounts(self):
        return get_accounts_normal_etf

    @property
    def exchange(self):
        return exchange_account_normal


@shared_task(bind=True, base=CurrencyExchangerRunnerForAccountBeingClosed)
def exchange_account_being_closed(
    self: CurrencyExchangerRunnerForAccountBeingClosed, account_alias: str
) -> dict:
    """환전 실행 - 개별 계좌(해지 매도 계좌)"""
    try:
        return self.process(account_alias)
    except Exception as e:
        logger.info(f"[환전][해지 매도 계좌][오류] Account {account_alias} - {e}")
        raise e


@shared_task(bind=True, rate_limit="1/s", base=CurrencyExchangerRunnerForAccountNormal)
def exchange_account_normal(
    self: CurrencyExchangerRunnerForAccountNormal, account_alias: str
) -> dict:
    """환전 실행 - 개별 계좌(정상 계좌)"""
    try:
        return self.process(account_alias)
    except Exception as e:
        logger.info(f"[환전][정상 계좌][오류] Account {account_alias} - {e}")
        raise e
