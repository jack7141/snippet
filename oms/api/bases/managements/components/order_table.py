import pandas as pd
from api.bases.managements.models import OrderLog

ORDER_BOOK_TABLE_COLUMNS = [
    "code",
    "trd_type",
    "account",
    "order_price",
    "market_price",
    "ord_qty",
    "new_shares",
    "exchange_rate",
    "price_strategy",
    "status",
]

ORDER_LOG_COLUMNS = ["order_id", "code", "type", "status", "created"]
ORDER_LOG_TABLE_COLUMNS = ["order_id", "code", "type", "trd_type", "status", "created"]
INDEX_KEYS = ["code", "trd_type"]

ASK = "01"
BID = "02"


class ABSOrderTable(pd.DataFrame):
    _COLUMNS = None

    def __init__(self, *args, **kwargs):
        kwargs["columns"] = kwargs.get("columns", self._COLUMNS)
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return self.df.__repr__()

    @property
    def df(self):
        return pd.DataFrame(self)

    @property
    def has_orders_on_hold(self):
        return self.status.isin([OrderLog.STATUS.on_hold]).any()

    @property
    def is_completed(self):
        incomplete_cases = [
            OrderLog.STATUS.on_hold,
            OrderLog.STATUS.processing,
            OrderLog.STATUS.failed,
        ]
        return not self.status.isin(incomplete_cases).any()

    @property
    def has_completed_orders(self):
        return self.status.isin([OrderLog.STATUS.completed]).any()

    @property
    def ask_order(self) -> pd.DataFrame:
        return self.loc[(self.trd_type == ASK)]

    @property
    def bid_order(self) -> pd.DataFrame:
        return self.loc[(self.trd_type == BID)]

    def get_orders_on_hold(self):
        return self.loc[self.status.isin([OrderLog.STATUS.on_hold])]


class OrderLogSeries(pd.Series):
    @property
    def _constructor(self):
        return OrderLogSeries

    @property
    def _constructor_expanddim(self):
        return OrderLogTable


class OrderLogTable(ABSOrderTable):
    _COLUMNS = ORDER_LOG_TABLE_COLUMNS

    @property
    def _constructor(self):
        return OrderLogTable

    @property
    def _constructor_sliced(self):
        return OrderLogSeries

    @classmethod
    def build(cls, order_id: str):
        queryset = OrderLog.objects.filter(order_id=order_id)
        instance = cls(queryset.values(*ORDER_LOG_COLUMNS).iterator())
        instance["trd_type"] = instance.apply(
            lambda row: cls.get_trd_type(row["type"]), axis=1
        )
        return instance

    @classmethod
    def build_latest(cls, order_id: str):
        instance = cls.build(order_id=order_id)
        latest_order_table = instance.loc[instance.groupby("code").created.idxmax()]
        return latest_order_table

    @staticmethod
    def get_trd_type(order_log_type: int):
        if order_log_type // 10 == 1:
            return BID
        elif order_log_type // 10 == 2:
            return ASK
        else:
            raise TypeError(f"Unsupported trd_type({order_log_type})")


class OrderBookSeries(pd.Series):
    @property
    def _constructor(self):
        return OrderBookSeries

    @property
    def _constructor_expanddim(self):
        return OrderBookTable


class OrderBookTable(ABSOrderTable):
    _COLUMNS = ORDER_BOOK_TABLE_COLUMNS

    @property
    def _constructor(self):
        return OrderBookTable

    @property
    def _constructor_sliced(self):
        return OrderBookSeries

    @property
    def ask_order(self):
        return self.loc[(self.trd_type == ASK) & (self.new_shares != 0)]

    @property
    def bid_order(self):
        return self.loc[(self.trd_type == BID) & (self.new_shares != 0)]

    def update_status(self, order_log_table: OrderLogTable):
        if not order_log_table.empty:
            indexed_order_log_table = order_log_table.set_index(keys=INDEX_KEYS)
            self.set_index(keys=INDEX_KEYS, inplace=True)
            self.update(indexed_order_log_table["status"])
            self["status"] = self["status"].astype(int)
            self.reset_index(inplace=True)
