import requests
import pandas as pd
from typing import List
from django.core.cache import caches


class UnsupportedTicker(RuntimeError):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


class TickerStager:
    page_size = 100

    def __init__(self, api_url):
        self._api_url = api_url

    def to_str(self, symbols: List[str]) -> str:
        if not isinstance(symbols, str):
            return ",".join(set(symbols))
        return symbols

    def get_prices(self, symbols):
        if isinstance(symbols, list):
            symbols = pd.Index(symbols)
        if symbols.empty:
            return pd.DataFrame().rename_axis("symbol")

        master_df = pd.DataFrame(self.get_master(symbols=symbols))
        if master_df.empty:
            raise UnsupportedTicker(f"symbols({set(symbols)}) are unavailable assets")

        master_df.set_index("symbol", inplace=True)

        # tradable asset
        row_indexer = (master_df["nationCode"] == "US") & master_df["expireDate"].isna()
        master_df = master_df.loc[row_indexer, :]
        if not symbols.isin(master_df.index).all():
            raise UnsupportedTicker(
                f"symbols({set(symbols) - set(master_df.index)}) are unavailable assets"
            )

        quote_df = pd.DataFrame(self.get_quote(symbols=master_df.index)).set_index(
            "symbol"
        )
        price_df = pd.merge(
            left=master_df[["prevClose"]],
            right=quote_df,
            left_index=True,
            right_index=True,
            how="outer",
        )
        price_sr = price_df.apply(func=self.calc_price, axis=1)
        return price_sr.to_frame(name="price")

    def get_close_prices_on_date(self, symbols, date):
        if isinstance(symbols, list):
            symbols = pd.Index(symbols)
        if symbols.empty:
            return pd.DataFrame().rename_axis("symbol")

        master_df = pd.DataFrame(self.get_master(symbols=symbols))
        if master_df.empty:
            raise UnsupportedTicker(f"symbols({set(symbols)}) are unavailable assets")

        master_df.set_index("symbol", inplace=True)

        # tradable asset
        row_indexer = (master_df["nationCode"] == "US") & master_df["expireDate"].isna()
        master_df = master_df.loc[row_indexer, :]
        if not symbols.isin(master_df.index).all():
            raise UnsupportedTicker(
                f"symbols({set(symbols) - set(master_df.index)}) are unavailable assets"
            )

        close_data = self.get_close(symbols=master_df.index, date=date)
        if not close_data:
            raise ValueError(f"No data on {date}")

        close_df = pd.DataFrame(close_data).set_index("symbol")
        return close_df[["open", "last"]]

    def get_close(self, symbols, date=None) -> pd.DataFrame:
        params = {"symbols": self.to_str(symbols), "page_size": self.page_size}
        if date is not None:
            params["date"] = date  # str, yyyymmdd | yyyy-mm-dd

        resp = requests.get(f"{self._api_url}/api/v1/infomax/close", params=params)
        resp.raise_for_status()
        return resp.json()["data"]

    def get_master(self, symbols) -> pd.DataFrame:
        resp = requests.get(
            f"{self._api_url}/api/v1/infomax/master",
            params={"symbols": self.to_str(symbols), "page_size": self.page_size},
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def get_bid(self, symbols) -> pd.DataFrame:
        resp = requests.get(
            f"{self._api_url}/api/v1/infomax/bid",
            params={"symbols": self.to_str(symbols), "page_size": self.page_size},
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def get_quote(self, symbols) -> pd.DataFrame:
        resp = requests.get(
            f"{self._api_url}/api/v1/infomax/quote",
            params={"symbols": self.to_str(symbols), "page_size": self.page_size},
        )
        resp.raise_for_status()
        return resp.json()["data"]

    @staticmethod
    def calc_price(row):
        if pd.isna(row["last"]):
            return float(row["prevClose"])
        return float(row["last"])


class CachedTickerStager(TickerStager):
    cache = caches["price"]

    def get_prices(self, symbols):
        cached_prices = self.get_cached_last_prices(symbols=symbols)
        missed = set(symbols) - set(cached_prices.index)
        last_prices = super(CachedTickerStager, self).get_prices(symbols=list(missed))
        self.cache.set_many({i: row.to_dict() for i, row in last_prices.iterrows()})
        prices = cached_prices.append(last_prices)
        self.checksum_symbols(symbols=symbols, prices=prices)
        return prices

    def get_cached_last_prices(self, symbols):
        if isinstance(symbols, pd.Index):
            symbols = symbols.to_list()
        symbols = set(symbols)
        prices = pd.DataFrame(self.cache.get_many(symbols)).transpose()
        prices.index.name = "symbol"
        return prices

    @classmethod
    def flush_all(cls):
        cls.cache.clear()

    def checksum_symbols(self, symbols, prices):
        symbols = pd.Index(symbols)
        symbol_exist_flags = symbols.isin(prices.index)

        if symbol_exist_flags.all():
            return True
        raise UnsupportedTicker(
            f"Not supported symbols: {symbols[~symbol_exist_flags]}"
        )
