from abc import ABC, abstractstaticmethod
import logging

import requests

from django.conf import settings

from api.bases.core.requests_with_retry import get_requests_retry_session_with_logging
from api.bases.accounts.models import Account
from api.bases.managements.components.exchange.currencies import ForeignCurrency
from api.bases.managements.components.exchange.results import (
    AbstractAPIResultFromGetExchangeableCurrencies,
    AbstractAPIResultFromConvertUSDToKRW,
    KBExchangeAPIResultFromGetExchangeableCurrencies,
    KBExchangeAPIResultFromConvertUSDToKRW,
)
from common.exceptions import PreconditionFailed

logger = logging.getLogger(__name__)

TR_BACKEND = settings.TR_BACKEND


class AbstractExchangeAPI(ABC):
    host = "https://<api-host>"
    paths = dict(exchange_apply="/api/v1/<vendor_code>/exchange/apply")
    result_classes = dict(
        get_exchangeable_currencies=AbstractAPIResultFromGetExchangeableCurrencies,
        convert_usd_to_krw=AbstractAPIResultFromConvertUSDToKRW,
    )

    @classmethod
    def get_uri_by_function_name(cls, function_name: str) -> str:
        return f"{cls.host}{cls.paths[function_name]}"

    @classmethod
    def get_exchangeable_currencies(
        cls, account: Account
    ) -> AbstractAPIResultFromGetExchangeableCurrencies:
        """[TR] 환전 가능 금액 조회"""

        response = get_requests_retry_session_with_logging().get(
            cls.get_uri_by_function_name("exchange_apply"),
            params=cls._build_params_for_get_exchangeable_currencies(account),
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            response_data = response.json()
            result = cls.result_classes["get_exchangeable_currencies"](response_data)
            result.raise_if_failed()
            raise e.__class__(response_data)

        if not response:  # 어떤 상황인지 확인 필요
            raise PreconditionFailed("Empty response from currency exchange API")

        return cls.result_classes["get_exchangeable_currencies"](response.json())

    @classmethod
    def convert_usd_to_krw(
        cls, account: Account, usd_currency: ForeignCurrency
    ) -> AbstractAPIResultFromConvertUSDToKRW:
        """[TR] 환전 신청"""

        response = get_requests_retry_session_with_logging().post(
            cls.get_uri_by_function_name("exchange_apply"),
            json=cls._build_payload_for_convert_usd_to_krw(account, usd_currency),
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            response_data = response.json()
            result = cls.result_classes["convert_usd_to_krw"](response_data)
            result.raise_if_failed()
            raise e.__class__(response_data)

        return cls.result_classes["convert_usd_to_krw"](response.json())

    @abstractstaticmethod
    def _build_params_for_get_exchangeable_currencies(account: Account) -> dict:
        pass

    @abstractstaticmethod
    def _build_payload_for_convert_usd_to_krw(
        account: Account, usd_currency: ForeignCurrency
    ) -> dict:
        pass


class KBExchangeAPI(AbstractExchangeAPI):
    host = TR_BACKEND["KB"].HOST
    paths = dict(exchange_apply="/api/v1/kb/exchange/apply")
    result_classes = dict(
        get_exchangeable_currencies=KBExchangeAPIResultFromGetExchangeableCurrencies,
        convert_usd_to_krw=KBExchangeAPIResultFromConvertUSDToKRW,
    )

    @staticmethod
    def _build_params_for_get_exchangeable_currencies(account: Account) -> dict:
        return dict(
            account=account.account_number,
            exchange_currency_code=ForeignCurrency.USD_CURRENCY_CODE,
            jb_code=ForeignCurrency.USD2KRW,
            exchange_rate=0,
            foreign_currency_amt=0,
        )

    @staticmethod
    def _build_payload_for_convert_usd_to_krw(
        account: Account, usd_currency: ForeignCurrency
    ) -> dict:
        return dict(
            account=account.account_number,
            exchange_currency_code=ForeignCurrency.USD_CURRENCY_CODE,
            jb_code=ForeignCurrency.USD2KRW,
            exchange_rate=usd_currency.exchange_rate,
            foreign_currency_amt=usd_currency.exchange_amount,
        )


EXCHANGE_API_BY_VENDOR_CODE = dict(kb=KBExchangeAPI)
