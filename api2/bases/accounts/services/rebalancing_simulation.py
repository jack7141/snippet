from datetime import datetime
import math

import requests
import pandas as pd

from django.conf import settings
from django.core.cache import caches
from django.utils import timezone

from common.mixins import PortfolioMapMixin
from common.utils import get_local_today
from api.bases.accounts.models import Account
from api.bases.managements.components.exchange.currencies import ForeignCurrency
from api.bases.managements.components.data_stagers import CachedTickerStager
from api.bases.managements.components.order_account import OrderRequester
from api.bases.managements.order_router.order_manager import OrderManagement
from api.bases.orders.models import Event

TR_BACKEND = settings.TR_BACKEND
INFOMAX_BACKEND = settings.INFOMAX_BACKEND


class AccountRebalancingSimulationService(PortfolioMapMixin):
    CACHE_TIMEOUT = 60 * 60 * 24  # 24 hours
    REQUIRED_BASE_MARGIN_TO_REBALANCE = 0.02

    def __init__(self, account: Account, requester: OrderRequester):
        self.account = account
        self.requester = requester

    def get_status(self):
        exchange_rate = self._get_exchange_rate()
        port_data = self._get_port_data()

        try:
            om = OrderManagement(
                account_alias=self.account.account_alias,
                data_stager=CachedTickerStager(api_url=INFOMAX_BACKEND.API_HOST),
                portfolio=port_data,
                exchange_rate=exchange_rate,
                vendor_code=self.account.vendor_code,
                mode=Event.MODES.rebalancing,
            )
        except requests.exceptions.HTTPError as e:
            return dict(
                is_succeeded=False,
                executed_at=timezone.now(),
                error=dict(status_code=e.response.status_code, message=e.response.text),
            )
        except Exception as e:
            return dict(
                is_succeeded=False,
                executed_at=timezone.now(),
                error=dict(error=str(e)),
            )

        return dict(
            is_succeeded=True,
            executed_at=timezone.now(),
            base=om._proxy.base,
            all_shares_value=om._proxy.shares["evaluate_amount"].sum(),
            min_deposit_to_rebalance=self._calc_min_deposit_to_rebalance(om),
            rebalancing_simulation_report=self._format_report_from_summary(
                om.get_summary()
            ),
        )

    def store_in_cache(self, data):
        return caches["account_status"].set(
            self.account.account_alias, data, self.CACHE_TIMEOUT
        )

    def refresh(self):
        data = self.get_status()
        self.store_in_cache(data)

    def _get_exchange_rate(self):
        return ForeignCurrency.get_exchange_rate(
            api_base=TR_BACKEND[str(self.account.vendor_code).upper()].HOST
        )

    def _get_port_data(self):
        kst_today = get_local_today()
        portfolio_map = self.get_portfolio_map(
            filter_date=kst_today.strftime("%Y-%m-%d")
        )
        strategy_code = f"{self.account.strategy_code:02}"
        risk_type_code = str(self.account.risk_type)
        return portfolio_map[strategy_code].get(risk_type_code)["port_data"]

    @classmethod
    def _calc_min_deposit_to_rebalance(cls, om: OrderManagement):
        all_shares_value = om._proxy.shares["evaluate_amount"].sum()
        reb_deposit_ratio = 1 - om.rebalancing_portfolio.weight.sum()
        required_cur_deposit_ratio = om.slippage_threshold + reb_deposit_ratio
        required_base_denominator = (
            1 - (om.min_deposit_ratio + om.deposit_buffer_ratio)
        ) * (1 - required_cur_deposit_ratio)
        required_base_upper_band = (
            all_shares_value * (1 + cls.REQUIRED_BASE_MARGIN_TO_REBALANCE)
        ) / required_base_denominator
        required_base = all_shares_value / required_base_denominator
        required_base_lower_band = (
            all_shares_value * (1 - cls.REQUIRED_BASE_MARGIN_TO_REBALANCE)
        ) / required_base_denominator
        return dict(
            upper=math.ceil(required_base_upper_band - om._proxy.base + 1),
            base=math.ceil(required_base - om._proxy.base + 1),
            lower=math.ceil(required_base_lower_band - om._proxy.base + 1),
        )

    @classmethod
    def _format_report_from_summary(cls, summary):
        weight_column_indexer = summary.columns.str.contains("weight")
        weight_columns = summary.columns[weight_column_indexer]
        non_weight_columns = summary.columns[~weight_column_indexer]
        deposit_info = (1 - summary[weight_columns].sum(axis=0)).round(3)
        return "\n\n".join(
            [
                cls._format_summary(
                    data=summary[weight_columns], desc="Order Basket Weight"
                ),
                cls._format_summary(data=deposit_info, desc="Deposit ratio"),
                cls._format_summary(
                    data=summary[non_weight_columns], desc="Order Basket Detail"
                ),
            ]
        )

    @staticmethod
    def _format_summary(data, desc=""):
        body = ""
        if desc:
            body += f"# {desc} at {datetime.now().isoformat()}\n"
        if isinstance(data, pd.DataFrame):
            body += data.to_string(float_format=lambda x: "%.3f" % x)
        else:
            body += str(data)
        return body
