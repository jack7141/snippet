import datetime

import pandas as pd

from django.conf import settings

from common.mixins import PortfolioMapMixin
from common.utils import convert_date_to_yyyy_mm_dd
from api.bases.managements.components.data_stagers import TickerStager
from api.bases.managements.portfolio.manager import PortfolioManager
from api.bases.managements.portfolio.price_engine import OrderPriceEngine


TR_BACKEND = settings.TR_BACKEND
INFOMAX_BACKEND = settings.INFOMAX_BACKEND

MIN_DEPOSIT_RATIO_DEFAULT = 0.05
DEPOSIT_BUFFER_RATIO_DEFAULT = 0.02


class ActualPortfolioReportService(PortfolioMapMixin):
    def __init__(
        self,
        universe_index: int,
        strategy_code: int,
        date: datetime.date,
        base_amount: float,
        exchange_rate: float,
        min_deposit_ratio: float = MIN_DEPOSIT_RATIO_DEFAULT,
        deposit_buffer_ratio: float = DEPOSIT_BUFFER_RATIO_DEFAULT,
    ) -> None:
        self.universe_index = universe_index
        self.strategy_code = strategy_code
        self.date = date
        self.base_amount = base_amount
        self.exchange_rate = exchange_rate
        self.min_deposit_ratio = min_deposit_ratio
        self.deposit_buffer_ratio = deposit_buffer_ratio

        self.data_stager = TickerStager(api_url=INFOMAX_BACKEND.API_HOST)

    @property
    def max_order_base_amount(self) -> float:
        return self.base_amount * (
            1 - (self.min_deposit_ratio + self.deposit_buffer_ratio)
        )

    def show(self) -> None:
        print(self._get_master_header())

        port_seq_by_risk_type = self.get_port_seq_by_risk_type(
            universe_index=self.universe_index,
            strategy_code=self.strategy_code,
            filter_date=convert_date_to_yyyy_mm_dd(self.date),
        )

        for risk_type, port_seq in port_seq_by_risk_type.items():
            rebalancing_portfolio = self.get_rebalancing_portfolio_with_ap_weight(
                port_seq
            )
            print(self._get_header(risk_type, port_seq))
            print(rebalancing_portfolio)
            print("\n")

    def _get_master_header(self) -> str:
        return (
            f"# date: {self.date}, base_amount: {self.base_amount:,}, exchange_rate: {self.exchange_rate}, "
            f"min_deposit_ratio: {self.min_deposit_ratio}, deposit_buffer_ratio: {self.deposit_buffer_ratio}\n"
        )

    def _get_header(self, risk_type: str, port_seq: dict) -> str:
        return f"* universe_index: {self.universe_index}, strategy_code: {self.strategy_code}, risk_type: {risk_type}, port_seq: {port_seq['port_seq']}\n"

    def get_rebalancing_portfolio_with_ap_weight(self, port_seq: dict) -> pd.DataFrame:
        portfolio_manager = PortfolioManager(
            portfolio=port_seq["port_data"], price_engine=OrderPriceEngine()
        )
        symbols = portfolio_manager.model_portfolio.index.to_list()
        close_prices = self.data_stager.get_close_prices_on_date(
            symbols, convert_date_to_yyyy_mm_dd(self.date)
        ).astype(float)

        open_rebalancing_portfolio = self.get_rebalancing_portfolio_by_price_type(
            portfolio_manager, close_prices, "open"
        ).add_suffix("_open")
        close_rebalancing_portfolio = self.get_rebalancing_portfolio_by_price_type(
            portfolio_manager, close_prices, "last"
        ).add_suffix("_close")
        rebalancing_portfolio = open_rebalancing_portfolio.join(
            close_rebalancing_portfolio
        )
        rebalancing_portfolio["ap_weight_open_close_diff"] = abs(
            rebalancing_portfolio["ap_weight_open"]
            - rebalancing_portfolio["ap_weight_close"]
        )
        return rebalancing_portfolio

    def get_rebalancing_portfolio_by_price_type(
        self,
        portfolio_manager: PortfolioManager,
        close_prices: pd.DataFrame,
        price_type: str,  # "open" | "last"
        emphasis: str = "weight_first",
    ) -> pd.DataFrame:
        prices = self.format_prices(close_prices[price_type].to_frame(name="price"))
        rebalancing_portfolio = portfolio_manager.calc_rebalancing_portfolio(
            self.max_order_base_amount, prices, emphasis=emphasis
        )
        rebalancing_portfolio["usd_price"] = prices["usd_price"]
        rebalancing_portfolio["krw_price"] = prices["krw_price"]
        rebalancing_portfolio["amount"] = (
            rebalancing_portfolio["krw_price"] * rebalancing_portfolio["shares"]
        )
        rebalancing_portfolio["ap_weight"] = (
            rebalancing_portfolio["amount"] / self.base_amount
        )
        return rebalancing_portfolio

    def format_prices(self, prices_df: pd.DataFrame) -> pd.DataFrame:
        prices_df["usd_price"] = prices_df.price
        prices_df["krw_price"] = prices_df.price * self.exchange_rate
        prices_df["exchange_rate"] = self.exchange_rate
        prices_df.index.name = "code"
        return prices_df
