import logging
import pandas as pd
import pytz
import requests
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone
from typing import List

from api.bases.managements.models import ASK, OrderLog, MAX_NOTE_SIZE
from api.bases.managements.components.abc import (
    ABCOrderManagement,
    ABCOrderAccountProxy,
)
from common.exceptions import StopOrderOperation
from common.decorators import cached_property


ALL_ORDERS = "0"
EXECUTED_ORDERS = "1"
UNEXECUTED_ORDERS = "2"
RA_CHANNEL_NAME = "RA(일임사)"

logger = logging.getLogger(__name__)


class OrderAccountProxy(ABCOrderAccountProxy):
    SHARES_COLUMNS = [
        "code",
        "buy_price",
        "shares",
        "evaluate_amount",
        "gross_loss",
        "gross_loss_ratio",
    ]

    def __init__(
        self,
        management: ABCOrderManagement,
        testbed_krx_tickers=None,
        is_ignore_personal_trade=False,
    ):
        super().__init__(management=management)
        self.is_ignore_personal_trade = is_ignore_personal_trade
        self.testbed_krx_tickers = testbed_krx_tickers or []
        self.api_base = self.manager.api_base
        self.vendor_code = self.manager.vendor_code
        self.requester = OrderRequesterWithAccountAPI(
            api_base=self.api_base, vendor_code=self.vendor_code
        )

        self.set_assets()
        won_exchange_amt = self.requester.get_account_balances(
            account_number=self.manager.account_number
        )
        self.base -= won_exchange_amt
        self._shares_prices = self.requester.get_account_stocks(
            account_number=self.manager.account_number
        )
        self.checksum_trade_history()

    @property
    def base(self):
        return self._base

    @base.setter
    def base(self, value):
        if value < 0:
            raise ValueError("Can't assign negative value for base amount")
        self._base = value

    @cached_property
    def current_portfolio(self):
        _cur_port = self.shares[
            ["code", "buy_price", "shares", "evaluate_amount"]
        ].set_index("code")
        _cur_port["weight"] = _cur_port.evaluate_amount / self.manager.max_ord_base
        return _cur_port

    def reset_current_portfolio_cache(self):
        if hasattr(self, "_current_portfolio"):
            del self._current_portfolio

    @property
    def shares_prices(self):
        return self._shares_prices

    def set_assets(self):
        brokerage_account = self._get_account_from_brokerage()
        self.base = brokerage_account["base"]
        self.shares = brokerage_account["shares"]

        # Set self.shares excluding testbed_krx_tickers
        self.shares = self.shares.loc[
            ~self.shares.code.isin(self.testbed_krx_tickers)
        ].reset_index(drop=True)

    def _get_account_from_brokerage(self):
        """
        Get account status from brokerage

        :rtype: dict; {base: int, shares: DataFrame}
        :returns:
            Account status from brokerage
            {
                "base": 978835,  # 계좌 평가액
                "shares":  # 보유 종목 정보
                           code  buy_price  shares  evaluate_amount  gross_loss  gross_loss_ratio
                    0   A337140      16290       1            12425       -3865            -23.72
                    1      MTVR      68211       3            64045       -4166             -6.10
                    2      SUBS      95884       4            90419       -5465             -5.69
                    3       DBO      45488       2            45426         -62             -0.13
                    4       DBB      59644       2            55954       -3690             -6.18
                    5       EWY      85087       1            81587       -3500             -4.11
                    6       EWJ      72189       1            70217       -1972             -2.73
                    7      SPTI      74808       2            75150         342              0.45
                    8      SCHP     222571       3           220365       -2206             -0.99
                    9      CORN      75758       2            71887       -3871             -5.09
                    10     SOYB      71974       2            69108       -2866             -3.98
                    11      VWO      53065       1            52003       -1062             -2.00
                    [12 rows x 6 columns]
            }
        """

        def _get_shares_from_stocks(stocks):
            return pd.DataFrame(
                [
                    {
                        "code": item.get("stock_code"),
                        "buy_price": item.get("buy_amt"),
                        "shares": item.get("poss_ord_qty"),
                        "evaluate_amount": item.get("eval_amt"),
                        "gross_loss": item.get("unreliz_pl"),
                        "gross_loss_ratio": item.get("unreliz_pl_ratio"),
                    }
                    for item in stocks
                ],
                columns=self.SHARES_COLUMNS,
            )

        assets = self.requester.get_account_assets(self.manager.account_number)
        return dict(
            base=assets.get("net_asset_appr_amt", 0),
            shares=_get_shares_from_stocks(assets.get("stocks") or []),
        )

    def checksum_trade_history(self):
        if self.is_ignore_personal_trade:
            return True

        resp = self.requester.request_trade_history(
            account_number=self.manager.account_number, executed_flag=ALL_ORDERS
        )
        if not resp:
            return True

        response = resp.json()
        trades = response.get("trades", [])
        if not trades:
            return True

        trade_df = pd.DataFrame(trades)
        has_unsupported_order_tool = RA_CHANNEL_NAME != trade_df.order_tool_name
        if has_unsupported_order_tool.any():
            raise StopOrderOperation(
                f"Has invalid transaction history: "
                f"{trade_df.loc[has_unsupported_order_tool].values}"
            )
        return True

    def get_input_amount(self):
        resp = self.requester.request_base_amount(
            account_alias=self.manager.account.account_alias
        )
        return resp["baseAmt"]


class OrderAccountProxyForSell(OrderAccountProxy):
    """
    해지 매도 전용 OrderAccountProxy

    - 미지원 종목 포함 시에도 매도 청산 진행
    """

    def __init__(self, management: ABCOrderManagement):
        # 지원하지 않는 종목은 제외하고 처리하기 때문에 OrderAccountProxy와 달리 testbed_krx_tickers(지원하지 않는 종목)를 사용하지 않음
        super().__init__(
            management, testbed_krx_tickers=None, is_ignore_personal_trade=True
        )

    def set_assets(self):
        brokerage_account = self._get_account_from_brokerage()
        self.base = brokerage_account["base"]
        self.shares = brokerage_account["shares"]

        # Get supported symbols
        supported_symbols = self._get_supported_symbols(self.shares.code.to_list())

        # Set self.shares excluding unsupported symbols
        self.shares = self.shares.loc[
            self.shares.code.isin(supported_symbols)
        ].reset_index(drop=True)

    def _get_supported_symbols(self, symbols):
        master_df = pd.DataFrame(self.manager.data_stager.get_master(symbols=symbols))
        if master_df.empty:
            return []

        row_indexer = (master_df["nationCode"] == "US") & master_df["expireDate"].isna()
        master_df = master_df.loc[row_indexer, :]
        return master_df.symbol.to_list()


class OrderRequester:
    SHARES_PRICES_COLUMNS = ["code", "price", "currency_code", "exchange_rate"]

    update_type_map = {
        "매수": OrderLog.TYPE.BID_REGISTER,
        "매수정정": OrderLog.TYPE.BID_AMEND,
        "매수취소": OrderLog.TYPE.BID_CANCEL,
        "매도": OrderLog.TYPE.ASK_REGISTER,
        "매도정정": OrderLog.TYPE.ASK_AMEND,
        "매도취소": OrderLog.TYPE.ASK_CANCEL,
    }

    def __init__(self, api_base, vendor_code):
        self.api_base = api_base
        self.vendor_code = vendor_code

    def request_base_amount(self, account_number):
        resp = requests.get(
            f"{self.api_base}/api/v1/{self.vendor_code}/accounts/{account_number}/amount/base"
        )
        return resp.json()

    def request_trade_history(self, account_number, executed_flag, from_date=None):
        if from_date is None:
            tz = pytz.timezone("America/New_York")
            from_date = timezone.now().astimezone(tz)

        resp = requests.get(
            f"{self.api_base}/api/v1/{self.vendor_code}/accounts/{account_number}/execution",
            params={
                "from_date": from_date.strftime("%Y%m%d"),
                "to_date": timezone.localtime().strftime("%Y%m%d"),
                "exec_sign": executed_flag,
            },
        )
        return resp

    def get_trade_history(
        self, account_number, min_update_seconds, executed_flag=UNEXECUTED_ORDERS
    ):
        tz_map = {
            "KST": pytz.timezone("Asia/Seoul"),
            "UTC": pytz.timezone("UTC"),
            "USD": pytz.timezone("America/New_York"),
        }

        tz = pytz.timezone("America/New_York")
        from_date = timezone.now().astimezone(tz)

        trades_df = pd.DataFrame()
        old_delta = timezone.now() - relativedelta(seconds=min_update_seconds)
        resp = self.request_trade_history(
            account_number=account_number,
            executed_flag=executed_flag,
            from_date=from_date,
        )

        if resp.json().get("trades", None):
            _trd_history = resp.json().get("trades")

            for item in _trd_history:
                currency_code = item.get("currency_code")
                req_date = pd.to_datetime(
                    item.get("order_date") + item.get("order_time"),
                    format="%Y%m%d%H%M%S",
                )

                # Todo. 환율정보가 미국인경우 미국시간 맞춰 처리하도록 해놨으나 증시별로 구분필요.
                if currency_code == "USD" and req_date.hour <= 14:
                    req_date += relativedelta(days=1)

                req_date = req_date.tz_localize(tz_map.get("KST"))
                req_date = req_date.tz_convert(tz_map.get("UTC"))

                item.update({"req_date": req_date})

            trades_df = pd.DataFrame(_trd_history)
            trades_df["order_time_tz"] = trades_df["order_time"].apply(
                lambda x: timezone.now()
                .strptime(from_date.strftime("%Y%m%d") + x, "%Y%m%d%H%M%S")
                .astimezone(tz)
                .strftime("%H%M%S")
            )
            trades_df["is_old"] = trades_df["req_date"] <= old_delta
            trades_df["trd_type"] = trades_df["trade_sec_name"].apply(
                lambda x: self.update_type_map.get(x)
            )
            trades_df["max_gap_pct"] = trades_df["trade_sec_name"].apply(
                lambda x: 3 if "매수" in x else 5
            )
        return trades_df

    def get_account_assets(self, account_number):
        resp = requests.get(
            f"{self.api_base}/api/v1/{self.vendor_code}/accounts/{account_number}/assets"
        )

        _shares = []
        resp.raise_for_status()

        return resp.json()

    def get_account_stocks(self, account_number):
        # 해외 계좌 잔고 평가조회
        resp = requests.get(
            f"{self.api_base}/api/v1/{self.vendor_code}/accounts/{account_number}/evaluate/stocks",
            params={"refe_curr_yn": 1},
        )

        _shares_prices = []
        resp.raise_for_status()

        _stocks = resp.json().get("stocks")
        if _stocks is not None and isinstance(_stocks, list):
            _stocks = [item for item in _stocks if item.get("holding_qty") > 0]
            _shares_prices = [
                {
                    "code": item.get("stock_code"),
                    "price": item.get("last"),
                    "currency_code": item.get("currency_type_name"),
                    "exchange_rate": item.get("basic_exchg_rate"),
                }
                for item in _stocks
            ]

        return pd.DataFrame(_shares_prices, columns=self.SHARES_PRICES_COLUMNS)

    def get_account_balances(self, account_number):
        # 계좌 잔고조회(TA-1001)
        resp = requests.get(
            f"{self.api_base}/api/v1/{self.vendor_code}/accounts/{account_number}/balances"
        )
        resp.raise_for_status()
        balances = resp.json()

        # 외화 예수금 원화환산액이 있는경우(배당금) 순자산 평가금액에서 제외처리
        return balances.get("won_exchange_amt", 0)

    def cancel_orders(
        self, order_queue_id, updatable_orders_df: pd.DataFrame
    ) -> List[OrderLog]:
        order_logs = []

        if updatable_orders_df.empty:
            return order_logs

        columns = [
            "order_no",
            "trd_type",
            "account",
            "update_type",
            "code",
            "exchange_rate",
            "market_price",
            "price",
            "org_price",
            "ord_qty",
            "req_date",
        ]

        trd_target = updatable_orders_df

        for item in trd_target[columns].to_dict(orient="records"):
            order_log, is_created = OrderLog.objects.get_or_create(
                order_id=order_queue_id,
                code=item.get("code"),
                type=item.get("trd_type"),
                status=OrderLog.STATUS.on_hold,
                order_price=item.get("price"),
                market_price=item.get("market_price"),
                currency_code=item.get("ex_code"),
                shares=item.get("ord_qty"),
            )

            resp = requests.put(
                f"{self.api_base}/api/v1/{self.vendor_code}/accounts/order",
                json={
                    "account": item.get("account"),
                    "code": item.get("code"),
                    "price": item.get("price"),
                    "exchange_rate": item.get("exchange_rate"),
                    "ex_code": "US",
                    "update_type": item.get("update_type"),
                    "order_no": item.get("order_no"),
                },
            )

            if is_created:
                order_log.ordered_at = timezone.now()

            if resp:
                resp = resp.json()
                order_log.status = OrderLog.STATUS.completed
                order_log.order_no = resp.get("order_no")
            else:
                order_log.status = OrderLog.STATUS.failed
                logger.warning(f"FAIL CANCEL ORDER: {resp.text}")
                error_msg = resp.json().get("msg")
                order_log.error_msg = str(error_msg)[:MAX_NOTE_SIZE]
            order_log.save()
            order_logs.append(order_log)
        return order_logs

    def update_orders(
        self, order_queue_id, updatable_orders_df: pd.DataFrame
    ) -> List[OrderLog]:
        order_logs = []

        if updatable_orders_df.empty:
            return order_logs

        old = updatable_orders_df[updatable_orders_df["is_old"] == True]
        gap = updatable_orders_df[updatable_orders_df["change_by_gap"] == True]
        columns = [
            "order_no",
            "trd_type",
            "account",
            "update_type",
            "code",
            "exchange_rate",
            "market_price",
            "price",
            "org_price",
            "ord_qty",
            "req_date",
        ]

        trd_target = None

        if not old.empty:
            trd_target = old
        elif not gap.empty:
            trd_target = gap

        if trd_target is None:
            return order_logs

        for item in trd_target[columns].to_dict(orient="records"):
            order_log, is_created = OrderLog.objects.get_or_create(
                order_id=order_queue_id,
                code=item.get("code"),
                type=item.get("trd_type"),
                status=OrderLog.STATUS.on_hold,
                order_price=item.get("price"),
                market_price=item.get("market_price"),
                currency_code=item.get("ex_code"),
                shares=item.get("ord_qty"),
            )
            resp = requests.put(
                f"{self.api_base}/api/v1/{self.vendor_code}/accounts/order",
                json={
                    "account": item.get("account"),
                    "code": item.get("code"),
                    "price": item.get("price"),
                    "exchange_rate": item.get("exchange_rate"),
                    "ex_code": "US",
                    "update_type": item.get("update_type"),
                    "order_no": item.get("order_no"),
                },
            )

            if is_created:
                order_log.ordered_at = timezone.now()

            if resp:
                resp = resp.json()
                OrderLog.objects.filter(
                    order_id=order_queue_id,
                    code=item.get("code"),
                    status=OrderLog.STATUS.processing,
                ).update(status=OrderLog.STATUS.skipped)

                order_log.order_no = resp.get("order_no")
                order_log.status = OrderLog.STATUS.processing
            else:
                order_log.status = OrderLog.STATUS.failed
                logger.warning(f"FAIL UPDATE ORDER: {resp.text}")
                error_msg = resp.json().get("msg")
                order_log.error_msg = str(error_msg)[:MAX_NOTE_SIZE]
            order_log.save()
            order_logs.append(order_log)
        return order_logs

    def request_orders(
        self, order_queue_id, order_book_table: pd.DataFrame
    ) -> List[OrderLog]:
        order_logs = []
        for item in order_book_table.to_dict(orient="records"):
            order_log, is_created = OrderLog.objects.get_or_create(
                order_id=order_queue_id,
                code=item.get("code"),
                type=OrderLog.TYPE.ASK_REGISTER
                if item.get("trd_type") == ASK
                else OrderLog.TYPE.BID_REGISTER,
                status=OrderLog.STATUS.on_hold,
                order_price=item.get("order_price"),
                market_price=item.get("market_price"),
                currency_code=item.get("ex_code"),
                shares=item.get("ord_qty"),
            )

            resp = requests.post(
                f"{self.api_base}/api/v1/{self.vendor_code}/accounts/order",
                json={
                    "account": item["account"],
                    "code": item["code"],
                    "price": item["order_price"],
                    "exchange_rate": item["exchange_rate"],
                    "trd_type": item["trd_type"],
                    "shares": item["ord_qty"],
                },
            )

            if is_created:
                order_log.ordered_at = timezone.now()

            if resp:
                order_log.status = OrderLog.STATUS.processing
                order_log.order_no = resp.json().get("order_no")
            else:
                order_log.status = OrderLog.STATUS.failed
                logger.warning(f"FAIL REQUEST ORDER: {resp.text}")
                error_msg = resp.json().get("msg")
                order_log.error_msg = str(error_msg)[:MAX_NOTE_SIZE]

            order_log.save()
            order_logs.append(order_log)

        return order_logs


class OrderRequesterWithAccountAPI(OrderRequester):
    def __init__(self, api_base, vendor_code):
        super().__init__(api_base, vendor_code)
        self.account_api_config = self._get_account_api_config()

    @classmethod
    def _get_account_api_config(cls):
        return dict(
            host=settings.LITCHI_ACCOUNT_BACKEND.API_HOST,
            token=settings.LITCHI_ACCOUNT_BACKEND.API_TOKEN,
            timeout=settings.LITCHI_ACCOUNT_BACKEND.TIMEOUT,
        )

    def _get_default_options_for_account_api(self):
        headers = self._get_default_headers_for_account_api()
        timeout = self._get_default_timeout_for_account_api()
        return dict(headers=headers, timeout=timeout)

    def _get_default_headers_for_account_api(self):
        return dict(Authorization=f"Token {self.account_api_config['token']}")

    def _get_default_timeout_for_account_api(self):
        return self.account_api_config["timeout"]

    def request_base_amount(self, account_alias):
        resp = requests.get(
            f"{self.account_api_config['host']}/api/v1/accounts/amounts/{account_alias}",
            **self._get_default_options_for_account_api(),
        )
        resp.raise_for_status()
        return resp.json()
