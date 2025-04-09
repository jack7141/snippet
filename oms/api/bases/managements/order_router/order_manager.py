import logging

import pandas as pd
from django.conf import settings

from api.bases.managements.components.abc import ABCOrderManagement
from api.bases.managements.components.data_stagers import TickerStager
from api.bases.managements.components.order_account import (
    OrderAccountProxy,
    OrderAccountProxyForSell,
)
from api.bases.managements.components.order_reporter import OrderReporter
from api.bases.managements.portfolio.manager import PortfolioManager
from api.bases.managements.portfolio.price_engine import OrderPriceEngine
from api.bases.managements.models import Queue
from api.bases.orders.models import Event

logger = logging.getLogger(__name__)
TR_BACKEND = settings.TR_BACKEND
INFOMAX_BACKEND = settings.INFOMAX_BACKEND

UPDATE_ORDER = 1
CANCEL_ORDER = 2

LONG_POSITION = "L"
SHORT_POSITION = "S"

TIME_SCHEDULE = {
    "full": {
        "Sell_New": {
            1: "10:00",
            2: "11:00",
            3: "12:00",
            4: "13:00",
            5: "14:00",
            6: "15:00",
        },
        "Sell_Adjust": {
            1: "10:10",
            2: "11:10",
            3: "12:10",
            4: "13:10",
            5: "14:10",
            6: "15:10",
        },
        "Sell_Cancel": {
            1: "10:20",
            2: "11:20",
            3: "12:20",
            4: "13:20",
            5: "14:20",
            6: "15:20",
        },
        "Long_New": {
            1: "10:30",
            2: "11:30",
            3: "12:30",
            4: "13:30",
            5: "14:30",
            6: "15:30",
        },
        "Long_Adjust": {
            1: "10:40",
            2: "11:40",
            3: "12:40",
            4: "13:40",
            5: "14:40",
            6: "15:40",
        },
        "Long_Cancel": {
            1: "10:50",
            2: "11:50",
            3: "12:50",
            4: "13:50",
            5: "14:50",
            6: "15:50",
        },
    },
    "early": {
        "Sell_New": {1: "10:00", 2: "11:00", 3: "12:00"},
        "Sell_Adjust": {1: "10:10", 2: "11:10", 3: "12:10"},
        "Sell_Cancel": {1: "10:20", 2: "11:20", 3: "12:20"},
        "Long_New": {1: "10:30", 2: "11:30", 3: "12:30"},
        "Long_Adjust": {1: "10:40", 2: "11:40", 3: "12:40"},
        "Long_Cancel": {1: "10:50", 2: "11:50", 3: "12:50"},
    },
    "test": {
        "Sell_New": {1: "17:00", 2: "17:30"},
        "Sell_Adjust": {1: "17:05", 2: "17:35"},
        "Sell_Cancel": {1: "17:10", 2: "17:40"},
        "Long_New": {1: "17:15", 2: "17:45"},
        "Long_Adjust": {1: "17:20", 2: "17:50"},
        "Long_Cancel": {1: "17:25", 2: "17:55"},
    },
}


class OrderManagement(ABCOrderManagement):
    def __init__(
        self,
        account_alias=None,
        portfolio=None,
        data_stager: TickerStager = None,
        exchange_rate=0.0,
        min_deposit_ratio=0.05,
        deposit_buffer_ratio=0.02,
        slippage_threshold=0.05,
        mode=None,
        vendor_code=None,
    ):
        """
        :param base: 투자원금
        :param portfolio: 포트폴리오
        Examples
        --------
        >> portfolio
        [
            {'code': 'IEF', 'weight': 0.7},
            {'code': 'VWO', 'weight': 0.05},
            {'code': 'SPY', 'weight': 0.25}
        ]
        :param prices: 가격 정보
        Examples
        --------
        >> prices
        [
            {'code': 'IEF', 'price': 122.03},
            {'code': 'VWO', 'price': 43.69},
            {'code': 'SPY', 'price': 338.28},
            {'code': 'FOSL', 'price': 5.88},
        ]

        usage:
        _port = [
            {'code': 'IEF', 'weight': 0.7},
            {'code': 'VWO', 'weight': 0.05},
            {'code': 'SPY', 'weight': 0.25}
        ]

        _prices = [
            {'code': 'IEF', 'price': 122.03},
            {'code': 'VWO', 'price': 43.69},
            {'code': 'SPY', 'price': 338.28},
            {'code': 'FOSL', 'price': 5.88},
        ]

        OM = OrderManagement(base=1000000,
                             portfolio=_port,
                             shares=_shares,
                             prices=_prices,
                             deposit_rate=0.05,
                             exchange_rate=1186.5)
        emphasis = 'strict_ratio'
        OM.calc_shares(emphasis=emphasis)
        """
        super().__init__(
            api_base=TR_BACKEND[str(vendor_code).upper()].HOST,
            vendor_code=vendor_code,
            account_alias=account_alias,
            mode=mode,
            exchange_rate=exchange_rate,
            min_deposit_ratio=min_deposit_ratio,
            deposit_buffer_ratio=deposit_buffer_ratio,
        )
        self.min_deposit_ratio = min_deposit_ratio
        self.testbed_krx_tickers = self.strategies.get("testbed_krx_tickers", [])
        self.is_ignore_personal_trade = self.strategies.get(
            "is_ignore_personal_trade", False
        )

        slippage_threshold = self.strategies.get(
            "slippage_threshold", slippage_threshold
        )
        if isinstance(slippage_threshold, float):
            pass
        else:
            slippage_threshold = float(slippage_threshold)

        self.slippage_threshold = slippage_threshold
        self._mode = mode

        self.data_stager = data_stager

        if mode == Event.MODES.sell:
            self._proxy = OrderAccountProxyForSell(management=self)
        else:
            self._proxy = OrderAccountProxy(
                management=self,
                testbed_krx_tickers=self.testbed_krx_tickers,
                is_ignore_personal_trade=self.is_ignore_personal_trade,
            )

        self._price_engine = OrderPriceEngine()

        self.portfolio_manager = PortfolioManager(
            portfolio=portfolio, price_engine=OrderPriceEngine()
        )

        _symbols = self.portfolio_manager.model_portfolio.index.union(
            self.current_portfolio.index
        ).to_list()
        _symbols = list(set(_symbols) - set(self.testbed_krx_tickers))
        self.prices = self.get_prices(symbols=_symbols)
        self.reporter = None

    def add_deposit(self, deposit):
        self._proxy.base += deposit

    @property
    def mode(self):
        if self._mode not in Event.MODES:
            raise KeyError(
                f"Unsupported mode {self._mode}, available Event modes: f{Event.MODES}"
            )
        return self._mode

    @property
    def rebalancing_portfolio(self):
        rebalancing_portfolio = getattr(self, "_rebalancing_portfolio", None)
        if rebalancing_portfolio is None:
            rebalancing_portfolio = self.portfolio_manager.calc_rebalancing_portfolio(
                max_ord_base=self.max_ord_base,
                asset_prices=self.prices,
                emphasis=self.emphasis,
            )
            setattr(self, "_rebalancing_portfolio", rebalancing_portfolio)
        return rebalancing_portfolio

    @property
    def order_basket(self):
        order_basket = getattr(self, "_order_basket", None)
        if order_basket is None:
            order_basket = self.create_order_basket(
                current_portfolio=self.current_portfolio,
                rebalancing_portfolio=self.rebalancing_portfolio,
                asset_prices=self.prices,
                testbed_krx_tickers=self.testbed_krx_tickers,
            )
            setattr(self, "_order_basket", order_basket)
        return order_basket

    @property
    def bid_order_basket(self):
        return self.order_basket.loc[self.order_basket.new_shares > 0]

    @property
    def ask_order_basket(self):
        return self.order_basket.loc[self.order_basket.new_shares < 0]

    def set_reporter(self, queue: Queue):
        self.reporter = OrderReporter(
            queue=queue,
            vendor_code=self.vendor_code,
            account_number=self.account_number,
            strategies=self.strategies,
        )

    def get_prices(self, symbols):
        prices_df = self.data_stager.get_prices(symbols=symbols)
        prices_df["usd_price"] = prices_df.price
        prices_df["krw_price"] = prices_df.price * self.exchange_rate
        prices_df["exchange_rate"] = self.exchange_rate
        prices_df.index.name = "code"
        return prices_df

    @property
    def is_rebalancing_condition_met(self):
        flag = self.portfolio_manager.is_rebalancing_condition_met(
            current_portfolio=self.current_portfolio,
            rebalancing_portfolio=self.rebalancing_portfolio,
            slippage_threshold=self.slippage_threshold,
        )
        return flag

    def create_order_basket(self, current_portfolio, rebalancing_portfolio, asset_prices, testbed_krx_tickers):
        current_without_exept_tickers = list(set(current_portfolio.index) - set(testbed_krx_tickers))
        current_portfolio = current_portfolio.loc[current_without_exept_tickers]
        order_basket = pd.DataFrame(
            {
                "shares": current_portfolio.shares,
                "new_shares": 0
            },
            columns=["shares", "new_shares", "krw_price", "usd_price", "buy_price"],
            index=self.portfolio_manager.model_portfolio.index.union(current_portfolio.index),
        ).fillna(0)

        assert self.mode in Event.MODES, f"mode({self.mode}) is must be one of Event"

        if self.mode == "sell":
            pass
        else:
            order_basket.loc[rebalancing_portfolio.index, "new_shares"] += rebalancing_portfolio.shares

        order_basket.loc[current_portfolio.index, "new_shares"] -= current_portfolio.shares
        order_basket.shares += order_basket.new_shares

        order_basket.loc[current_portfolio.index, "buy_price"] = current_portfolio.buy_price
        order_basket.loc[:, "krw_price"] = asset_prices.krw_price[order_basket.index]  # krw price without tax
        order_basket.loc[:, "usd_price"] = asset_prices.usd_price[order_basket.index]  # usd price without tax

        return order_basket

    def get_summary(self):
        summary = self.portfolio_manager.get_summary(
            model_portfolio=self.portfolio_manager.model_portfolio,
            rebalancing_portfolio=self.rebalancing_portfolio,
            current_portfolio=self.current_portfolio,
        )
        summary["usd_price"] = self.prices.loc[summary.index, "usd_price"]
        summary["exchange_rate"] = self.exchange_rate
        return summary
