from abc import ABC, abstractmethod, abstractproperty
from functools import cached_property
from dataclasses import dataclass

from api.bases.accounts.models import Account
from api.bases.managements.components.exchange.currencies import ForeignCurrency


# API
class APIResultError(Exception):
    pass


class APIResultFailureError(APIResultError):
    pass


class APIResultFailureRetryableError(APIResultFailureError):
    pass


class APIResultInconsistentExchangeRateError(APIResultFailureRetryableError):
    pass


class AbstractAPIResult(ABC):
    def __init__(self, data: dict) -> None:
        self.data = data

    @abstractproperty
    def tr_code(self) -> str:
        pass

    @abstractproperty
    def message(self) -> str:
        pass

    @abstractproperty
    def status(self) -> str:
        pass

    @abstractmethod
    def raise_if_failed(self) -> None:
        pass


class AbstractAPIResultFromGetExchangeableCurrencies(AbstractAPIResult):
    @abstractproperty
    def currency_map(self) -> dict[str, ForeignCurrency]:
        pass


class AbstractAPIResultFromConvertUSDToKRW(AbstractAPIResult):
    @abstractproperty
    def exchange_rate(self) -> float:
        """적용 환율(USD2KRW)"""
        pass

    @abstractproperty
    def exchangeable_amount(self) -> float:
        """환전 가능 금액(USD)"""
        pass

    @abstractproperty
    def requested_amount(self) -> float:
        """환전 요청 금액(USD)"""
        pass

    @abstractproperty
    def exchanged_amount(self) -> float:
        """환전 금액(KRW)"""
        pass


class KBExchangeAPIResultMixin:
    @cached_property
    def tr_code(self) -> str:
        return self.data.get("tr_code")

    @cached_property
    def message(self) -> str:
        return self.data.get("msg")

    @cached_property
    def status(self) -> str:
        return self.data.get("status")

    def raise_if_failed(self) -> None:
        if self.status is None:
            return

        if "error" in self.status.lower():
            raise APIResultFailureError(self.data)

    @cached_property
    def exchange_rate(self) -> float:
        """적용 환율(USD2KRW)"""
        return self.data.get("apply_exchange_rate")


class KBExchangeAPIResultFromGetExchangeableCurrencies(
    KBExchangeAPIResultMixin, AbstractAPIResultFromGetExchangeableCurrencies
):
    @cached_property
    def currency_map(self) -> dict[str, ForeignCurrency]:
        exchange_rate = self.data.get("apply_exchange_rate")
        return {
            currency["currency_code"]: ForeignCurrency(
                currency_code=currency["currency_code"],
                exchange_amount=currency["exchange_possible_amt"],
                exchange_rate=exchange_rate,
            )
            for currency in self.data.get("currencies", [])
        }


class KBExchangeAPIResultFromConvertUSDToKRW(
    KBExchangeAPIResultMixin, AbstractAPIResultFromConvertUSDToKRW
):
    @cached_property
    def exchangeable_amount(self) -> float:
        """환전 가능 금액(USD)"""
        return self.data.get("exchange_possible_amt")

    @cached_property
    def requested_amount(self) -> float:
        """환전 요청 금액(USD)"""
        return self.data.get("req_amt")

    @cached_property
    def exchanged_amount(self) -> float:
        """환전 금액(KRW)"""
        return self.data.get("exchange_amt")

    def raise_if_failed(self) -> None:
        if self.status is None:
            return

        if self.data.get("msg_code") in ("I698",):
            """code: message
            I698: 조회시점과 환전처리시점 환율이 다릅니다. 다시 처리하시기 바랍니다.
            """
            raise APIResultInconsistentExchangeRateError(self.data)

        if "error" in self.status.lower():
            raise APIResultFailureError(self.data)


# CurrencyExchanger
class CurrencyExchangerResult:
    pass


@dataclass
class CurrencyExchangerResultForNotExchangeable(CurrencyExchangerResult):
    account: Account

    @property
    def data(self):
        return dict(account_alias=self.account.account_alias)


@dataclass
class CurrencyExchangerResultForCompleted(CurrencyExchangerResult):
    account: Account
    result: AbstractAPIResultFromConvertUSDToKRW

    @property
    def data(self):
        return dict(
            account_alias=self.account.account_alias,
            exchange_rate=self.result.exchange_rate,
            exchangeable_amount=self.result.exchangeable_amount,
            requested_amount=self.result.requested_amount,
            exchanged_amount=self.result.exchanged_amount,
        )
