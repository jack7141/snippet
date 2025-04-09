import logging
from datetime import datetime

import numpy as np
import pandas as pd
from django.conf import settings

from api.bases.managements.components.abc import ABCOrderManagement
from api.bases.managements.components.data_stagers import TickerStager
from api.bases.managements.components.order_account import (
    OrderAccountProxy,
    OrderAccountProxyForSell,
    UNEXECUTED_ORDERS,
    ALL_ORDERS,
    EXECUTED_ORDERS,
)
from api.bases.managements.components.order_reporter import OrderReporter
from api.bases.managements.components.order_table import (
    OrderBookTable,
    OrderLogTable,
    ASK,
    BID,
)
from api.bases.managements.components.state import QueueStatusContext
from api.bases.managements.models import Queue, OrderLog
from api.bases.managements.portfolio.price_engine import OrderPriceEngine
from common.decorators import cached_property
from common.exceptions import PreconditionFailed

logger = logging.getLogger(__name__)
TR_BACKEND = settings.TR_BACKEND
INFOMAX_BACKEND = settings.INFOMAX_BACKEND

UPDATE_ORDER = 1
CANCEL_ORDER = 2

LONG_POSITION = "L"
SHORT_POSITION = "S"


class ExecutionManagement(ABCOrderManagement):
    def __init__(
        self,
        account_alias,
        order_queue_id,
        exchange_rate,
        data_stager: TickerStager,
        vendor_code,
        min_deposit_ratio=0.05,
        deposit_buffer_ratio=0.02,
        *args,
        **kwargs,
    ):
        super(ExecutionManagement, self).__init__(
            api_base=TR_BACKEND[str(vendor_code).upper()].HOST,
            account_alias=account_alias,
            vendor_code=vendor_code,
            exchange_rate=exchange_rate,
            min_deposit_ratio=min_deposit_ratio,
            deposit_buffer_ratio=deposit_buffer_ratio,
        )

        self.testbed_krx_tickers = self.strategies.get("testbed_krx_tickers", [])
        self.is_ignore_personal_trade = self.strategies.get(
            "is_ignore_personal_trade", False
        )

        self.data_stager = data_stager

        if isinstance(order_queue_id, Queue):
            self.order_queue = order_queue_id
        else:
            self.order_queue = Queue.objects.get(id=order_queue_id)

        if self.order_queue.mode == Queue.MODES.sell:
            self._proxy = OrderAccountProxyForSell(management=self)
        else:
            self._proxy = OrderAccountProxy(
                management=self,
                testbed_krx_tickers=self.testbed_krx_tickers,
                is_ignore_personal_trade=self.is_ignore_personal_trade,
            )

        self.unexecuted_trd_history = self._proxy.requester.get_trade_history(
            account_number=self.account_number,
            min_update_seconds=self.strategies.min_update_seconds,
            executed_flag=UNEXECUTED_ORDERS,
        )
        self._price_engine = OrderPriceEngine()
        self.reporter = OrderReporter(
            queue=self.order_queue,
            vendor_code=self.vendor_code,
            account_number=self.account_number,
        )
        self.status_context = QueueStatusContext(order_queue=self.order_queue)

    @property
    def order_position(self):
        if self.order_queue.mode in [Queue.MODES.bid]:
            return LONG_POSITION
        elif self.order_queue.mode in [Queue.MODES.sell, Queue.MODES.ask]:
            return SHORT_POSITION
        else:
            raise TypeError(f"{self.order_queue.mode} is not invalid position")

    @property
    def is_remaining_order_basket_empty(self):
        return (self.remaining_order_basket.shares == 0).all()

    @property
    def remaining_order_basket(self):
        remainders = pd.DataFrame(
            {"shares": 0},
            index=self.order_basket.index.union(self.current_portfolio.index),
        )
        remainders.loc[self.order_basket.index, "shares"] += self.order_basket.shares
        remainders.loc[
            self.current_portfolio.index, "shares"
        ] -= self.current_portfolio.shares

        assert (
            not remainders.shares.isna().any()
        ), f"order_basket has null values: {remainders}"
        return remainders.loc[self.order_basket.index, :]

    @cached_property
    def order_basket(self):
        _order_basket = self.order_queue.order_basket
        if _order_basket:
            _order_basket = pd.DataFrame(_order_basket).set_index("code")
            _order_basket.update(self.get_prices(symbols=_order_basket.index))
            return _order_basket
        return pd.DataFrame(_order_basket)

    def calc_order_basket(self, order_type_to_plan):
        position = order_type_to_plan["position"]
        long_short = 1 if position == "L" else -1
        _remaining_order_count = order_type_to_plan["remaining_number_of_order"] + 1
        _total_number_of_order = order_type_to_plan["total_number_of_order"]
        resp = self._proxy.requester.request_trade_history(
            account_number=self.account_number, executed_flag=EXECUTED_ORDERS
        )
        resp.raise_for_status()
        df_traded_info = pd.DataFrame(resp.json()["trades"])

        if df_traded_info.empty:
            self.order_basket["remaining_qty"] = self.order_basket["new_shares"]
        else:
            df_traded_info = df_traded_info.loc[
                df_traded_info.order_tool_name.isin(["RA(일임사)"])
            ].reset_index(drop=True)
            df_traded_info["trade_sec_name"] = df_traded_info["trade_sec_name"].map(
                {"매도": "S", "매도정정": "S", "매수": "L", "매수정정": "L"}
            )

            s_ticker_to_traded_qty = (
                df_traded_info.query(f"trade_sec_name=='{position}'")
                .groupby("code")
                .sum("exec_qty")["exec_qty"]
            )
            s_ticker_to_traded_qty = s_ticker_to_traded_qty * long_short
            self.order_basket["remaining_qty"] = self.order_basket[
                "new_shares"
            ].subtract(s_ticker_to_traded_qty, fill_value=0)

        self.order_basket[["new_shares", "remaining_qty"]] = self.order_basket[
            ["new_shares", "remaining_qty"]
        ].abs()

        self.order_basket["org_twap_qty"] = (
            self.order_basket["new_shares"]
            .div(_total_number_of_order)
            .round(0)
            .astype(int)
        )
        self.order_basket["new_twap_qty"] = (
            self.order_basket["remaining_qty"]
            .div(_remaining_order_count)
            .round(0)
            .astype(int)
        )

        self.order_basket["min_qty"] = order_type_to_plan["min_qty"]
        self.order_basket["order_now_qty"] = self.order_basket[
            ["org_twap_qty", "new_twap_qty", "min_qty"]
        ].max(axis=1)
        self.order_basket["order_now_qty"] = self.order_basket[
            ["order_now_qty", "remaining_qty"]
        ].min(axis=1)

        self.order_basket[["new_shares", "remaining_qty", "order_now_qty"]] = (
            self.order_basket[["new_shares", "remaining_qty", "order_now_qty"]]
            * long_short
        )

        return self.order_basket

    def route_orders(self, order_type_to_plan) -> list:
        order_logs = []

        if self.unexecuted_trd_history.empty:  # 미체결 종목이 없을시, 신규 주문 신청
            if self.is_remaining_order_basket_empty:
                self.status_context.transition(status=Queue.STATUS.completed)
                return order_logs

            self.reporter.write_body(data=self.order_basket, desc="주문 대상 종목")
            order_now = self.calc_order_basket(order_type_to_plan)
            order_now["new_shares"] = order_now["order_now_qty"]
            order_book_table = self.create_order_book(
                order_basket=order_now
            )  # 주문 장부 생성

            self.reporter.write_body(data=order_book_table, desc="주문 장부")

            if order_book_table.has_orders_on_hold:
                order_logs = self.execute_orders(order_book_table=order_book_table)
            else:
                self.status_context.transition(status=Queue.STATUS.failed)

        else:  # 정정 주문
            OrderLog.objects.complete_executed_orders(
                order_queue_id=self.order_queue.id,
                unexecuted_codes=self.unexecuted_trd_history.code,
            )
            order_logs = self.update_orders()
        return order_logs

    def execute_orders(self, order_book_table: OrderBookTable):
        order_logs = []

        if order_book_table.has_orders_on_hold:
            self.status_context.transition(status=Queue.STATUS.processing)

            order_logs = self._proxy.requester.request_orders(
                order_queue_id=self.order_queue.id,
                order_book_table=order_book_table.get_orders_on_hold(),
            )
        return order_logs

    def update_orders(self):
        order_logs = []
        updatable_orders_df = self.get_update_orders_df()
        # 정정가격, 주문가격 달라야 함.
        updatable_orders_df = updatable_orders_df.query("org_price != price")
        position_sr = updatable_orders_df.apply(
            lambda row: OrderLogTable.get_trd_type(row["trd_type"]), axis=1
        )

        if not updatable_orders_df.empty:
            updatable_orders_df.loc[
                position_sr == BID, "trd_type"
            ] = OrderLog.TYPE.BID_AMEND
            updatable_orders_df.loc[
                position_sr == ASK, "trd_type"
            ] = OrderLog.TYPE.ASK_AMEND

            self.reporter.write_body(
                data=updatable_orders_df,
                desc=f"Update Orders at {datetime.now().isoformat()}",
            )
            order_logs = self._proxy.requester.update_orders(
                order_queue_id=self.order_queue.id,
                updatable_orders_df=updatable_orders_df,
            )
        return order_logs

    def cancel_orders(self, position=None):
        order_logs = []

        cancelable_orders_df = self._get_updatable_orders_df(update_type=CANCEL_ORDER)
        if not cancelable_orders_df.empty:
            position_sr = cancelable_orders_df.apply(
                lambda row: OrderLogTable.get_trd_type(row["trd_type"]), axis=1
            )
            if position:
                if position == LONG_POSITION:
                    cancelable_orders_df = cancelable_orders_df[position_sr == BID]
                elif position == SHORT_POSITION:
                    cancelable_orders_df = cancelable_orders_df[position_sr == ASK]
                else:
                    raise KeyError(
                        f"unsupported position, select one of [{LONG_POSITION}, {SHORT_POSITION}]"
                    )

            if not cancelable_orders_df.empty:
                cancelable_orders_df.loc[
                    position_sr == BID, "trd_type"
                ] = OrderLog.TYPE.BID_CANCEL
                cancelable_orders_df.loc[
                    position_sr == ASK, "trd_type"
                ] = OrderLog.TYPE.ASK_CANCEL
                self.reporter.write_body(
                    data=cancelable_orders_df,
                    desc=f"Cancel Orders at {datetime.now().isoformat()}",
                )
                order_logs = self._proxy.requester.cancel_orders(
                    order_queue_id=self.order_queue.id,
                    updatable_orders_df=cancelable_orders_df,
                )
        return order_logs

    def get_update_orders_df(self):
        # 매도/매수에 대한 price 정책 추가 필요.
        # 주문 낸지 오래되지않았으나, 갭이 큰 경우
        # 주문 낸지 오래됐으나 갭이 작은경우
        # trading_df = pd.merge(old_history, self.prices, on='code')

        updatable_orders_df = self._get_updatable_orders_df(update_type=UPDATE_ORDER)
        if not updatable_orders_df.empty:
            price_strategy = (
                "buy"
                if not updatable_orders_df[
                    updatable_orders_df["trd_type"] == OrderLog.TYPE.BID_AMEND
                ].empty
                else "sell"
            )
            updatable_orders_df["price"] = self._price_engine.calc_prices(
                series=updatable_orders_df["price"],
                strategies=self.strategies,
                price_strategy=price_strategy,
            )
        return updatable_orders_df

    def _get_updatable_orders_df(self, update_type=UPDATE_ORDER):
        if self.unexecuted_trd_history.empty:
            return pd.DataFrame()

        old_history = self.unexecuted_trd_history[
            [
                "ord_no",
                "code",
                "ord_qty",
                "ord_price",
                "org_price",
                "trd_type",
                "max_gap_pct",
                "req_date",
                "is_old",
            ]
        ]

        prices = self.get_prices(symbols=old_history.code)
        updatable_orders_df = pd.merge(old_history, prices.reset_index(), on="code")

        updatable_orders_df["account"] = self.account_number
        updatable_orders_df["update_type"] = update_type
        updatable_orders_df["order_no"] = updatable_orders_df["ord_no"]
        updatable_orders_df["price_gap_pct"] = (
            (updatable_orders_df["ord_price"] / updatable_orders_df["price"]) - 1
        ) * 100
        updatable_orders_df["change_by_gap"] = (
            updatable_orders_df["price_gap_pct"] >= updatable_orders_df["max_gap_pct"]
        )
        updatable_orders_df["market_price"] = updatable_orders_df["price"]

        return updatable_orders_df

    def create_order_book(self, order_basket: pd.DataFrame) -> OrderBookTable:
        if "new_shares" not in order_basket.columns:
            raise PreconditionFailed("calc_shares() must be called to get order_book")

        if order_basket.empty:
            order_book_table = OrderBookTable.create(order_id=self.order_queue.id)
            return order_book_table

        order_basket = order_basket.reset_index()
        order_basket.rename(columns={"usd_price": "market_price"}, inplace=True)

        if self.order_position == LONG_POSITION:
            target_order_book = order_basket[order_basket["new_shares"] > 0].assign(
                trd_type=BID, price_strategy="buy"
            )
        elif self.order_position == SHORT_POSITION:
            target_order_book = order_basket[order_basket["new_shares"] < 0].assign(
                trd_type=ASK, price_strategy="sell"
            )
        else:
            raise TypeError(
                f"order position({self.order_position}) must be in [{LONG_POSITION}, {SHORT_POSITION}]"
            )

        no_order_book = order_basket[order_basket["new_shares"] == 0].assign(
            trd_type=BID, price_strategy=None
        )
        target_order_book["status"] = OrderLog.STATUS.on_hold
        no_order_book["status"] = OrderLog.STATUS.skipped

        if not target_order_book.empty:
            target_order_book["order_price"] = target_order_book.apply(
                func=lambda row: self._price_engine.calc_order_price(
                    row, strategies=self.strategies
                ),
                axis=1,
            )

        no_order_book["order_price"] = 0

        order_book_table = OrderBookTable(
            pd.concat([target_order_book, no_order_book], ignore_index=True)
        )
        order_book_table["ord_qty"] = order_book_table["new_shares"].apply(
            lambda x: np.abs(x)
        )
        order_book_table["account"] = self.account_number
        order_book_table["exchange_rate"] = self.exchange_rate
        return order_book_table

    def get_prices(self, symbols):
        prices_df = self.data_stager.get_prices(symbols=symbols)
        prices_df["exchange_rate"] = self.exchange_rate
        prices_df["usd_price"] = prices_df.price
        prices_df["krw_price"] = prices_df.price * self.exchange_rate
        prices_df.index.name = "code"
        return prices_df

    def save_report(self):
        self.reporter.save()
