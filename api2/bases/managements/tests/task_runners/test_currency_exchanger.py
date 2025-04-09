from typing import Union
from unittest.mock import call

import pytest
from pytest_mock import mocker, MockerFixture
import requests

from api.bases.accounts.models import Account
from api.bases.accounts.tests.factories import AccountFactory
from api.bases.managements.components.exchange.currencies import ForeignCurrency
from api.bases.managements.components.exchange.apis import KBExchangeAPI
from api.bases.managements.components.exchange.results import (
    KBExchangeAPIResultFromGetExchangeableCurrencies,
    KBExchangeAPIResultFromConvertUSDToKRW,
)
from api.bases.managements.components.exchange.exchanger import (
    CurrencyExchangerForAccountBeingClosed,
    CurrencyExchangerForAccountNormal,
)
from common.exceptions import PreconditionFailed

pytestmark = pytest.mark.django_db(databases=["default", "accounts"])


def create_account_etf_being_closed(vendor_code: str) -> Account:
    return AccountFactory(
        account_alias="20210516024403116595",
        vendor_code=vendor_code,
        account_number="12345678901",
        account_type=Account.ACCOUNT_TYPE.etf,
        status=Account.STATUS.account_sell_s,
    )


def create_account_etf_normal(vendor_code: str) -> Account:
    return AccountFactory(
        account_alias="20210516024403116595",
        vendor_code=vendor_code,
        account_number="12345678901",
        account_type=Account.ACCOUNT_TYPE.etf,
        status=Account.STATUS.normal,
    )


# TODO: Implement FakeAPI instead of using KBExchangeAPI
# TODO: Check raised exceptions in exchangers


class TestCurrencyExchangerForAccountBeingClosedWithKB:
    VENDOR_CODE = "kb"

    def test_process_normal_with_exchangeable_amount(
        self, mocker: MockerFixture
    ) -> None:
        """환전 가능 금액 보유, 정상 처리"""

        mocker.patch.object(
            KBExchangeAPI,
            f"get_exchangeable_currencies",
            return_value=KBExchangeAPIResultFromGetExchangeableCurrencies(
                {
                    "apply_exchange_rate": 1200.0,
                    "currencies": [
                        {
                            "currency_code": "USD",
                            "exchange_possible_amt": 1000.0,
                        },
                    ],
                }
            ),
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            return_value=KBExchangeAPIResultFromConvertUSDToKRW(
                {
                    "apply_exchange_rate": 1200.0,
                    "exchange_possible_amt": 20.0,
                    "req_amt": 20.0,
                    "exchange_amt": 24000.0,
                }
            ),
        )

        account = create_account_etf_being_closed(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountBeingClosed(account)
        result = manager.process()

        assert result.data == {
            "account_alias": account.account_alias,
            "exchange_rate": 1200.0,
            "exchangeable_amount": 20.0,
            "requested_amount": 20.0,
            "exchanged_amount": 24000.0,
        }

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_called_once_with(
            account,
            ForeignCurrency(
                currency_code="USD",
                exchange_amount=1000.0,
                exchange_rate=1200.0,
            ),
        )

        assert account.status == Account.STATUS.account_exchange_s

    def test_process_normal_with_unexchangeable_amount(
        self, mocker: MockerFixture
    ) -> None:
        """환전 가능 금액 미보유, 정상 처리"""

        mocker.patch.object(
            KBExchangeAPI,
            "get_exchangeable_currencies",
            return_value=KBExchangeAPIResultFromGetExchangeableCurrencies(
                {
                    "apply_exchange_rate": 1200.0,
                    "currencies": [
                        {
                            "currency_code": "USD",
                            "exchange_possible_amt": 0.0,
                        },
                    ],
                }
            ),
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            return_value=KBExchangeAPIResultFromConvertUSDToKRW({}),
        )

        account = create_account_etf_being_closed(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountBeingClosed(account)
        result = manager.process()

        assert result.data == {"account_alias": "20210516024403116595"}

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_not_called()

        assert account.status == Account.STATUS.account_exchange_s

    def test_process_normal_with_unexchangeable_minus_amount(
        self, mocker: MockerFixture
    ) -> None:
        """환전 가능 금액 미보유(마이너스 금액), 정상 처리(환전 실패 처리)"""

        mocker.patch.object(
            KBExchangeAPI,
            "get_exchangeable_currencies",
            return_value=KBExchangeAPIResultFromGetExchangeableCurrencies(
                {
                    "apply_exchange_rate": 1200.0,
                    "currencies": [
                        {
                            "currency_code": "USD",
                            "exchange_possible_amt": -10.0,
                        },
                    ],
                }
            ),
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            return_value=KBExchangeAPIResultFromConvertUSDToKRW({}),
        )

        account = create_account_etf_being_closed(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountBeingClosed(account)
        result = manager.process()

        assert result.data == {"account_alias": "20210516024403116595"}

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_not_called()

        assert account.status == Account.STATUS.account_exchange_f1

    def test_process_normal_with_no_exchangeable_currencies(
        self, mocker: MockerFixture
    ) -> None:
        """환전 가능 currency 미보유, 정상 처리"""

        mocker.patch.object(
            KBExchangeAPI,
            "get_exchangeable_currencies",
            return_value=KBExchangeAPIResultFromGetExchangeableCurrencies(
                {
                    "apply_exchange_rate": 1200.0,
                    "currencies": [
                        {
                            "currency_code": "KRW",
                            "exchange_possible_amt": 967473.0,
                        },
                    ],
                }
            ),
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            return_value=KBExchangeAPIResultFromConvertUSDToKRW({}),
        )

        account = create_account_etf_being_closed(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountBeingClosed(account)
        with pytest.raises(PreconditionFailed) as e:
            manager.process()

        assert str(e.value) == "No exchangeable currencies"

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_not_called()

        assert account.status == Account.STATUS.account_sell_s

    def test_process_error_from_get_exchangeable_currencies(
        self, mocker: MockerFixture
    ) -> None:
        """환전 가능 금액 보유 무관, [TR API] 환전 가능 금액 조회 → HTTPError"""

        mocker.patch.object(
            KBExchangeAPI,
            "get_exchangeable_currencies",
            side_effect=requests.exceptions.HTTPError,
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            return_value=KBExchangeAPIResultFromConvertUSDToKRW({}),
        )

        account = create_account_etf_being_closed(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountBeingClosed(account)
        with pytest.raises(requests.exceptions.HTTPError):
            manager.process()

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_not_called()

        assert account.status == Account.STATUS.account_sell_s

    def test_process_error_from_convert_usd_to_krw(self, mocker: MockerFixture) -> None:
        """환전 가능 금액 보유, [TR API] 환전 신청 → HTTPError"""

        mocker.patch.object(
            KBExchangeAPI,
            "get_exchangeable_currencies",
            return_value=KBExchangeAPIResultFromGetExchangeableCurrencies(
                {
                    "apply_exchange_rate": 1200.0,
                    "currencies": [
                        {
                            "currency_code": "USD",
                            "exchange_possible_amt": 1000.0,
                        },
                    ],
                }
            ),
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            side_effect=requests.exceptions.HTTPError,
        )

        account = create_account_etf_being_closed(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountBeingClosed(account)
        with pytest.raises(requests.exceptions.HTTPError):
            manager.process()

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_called_once_with(
            account,
            ForeignCurrency(
                currency_code="USD",
                exchange_amount=1000.0,
                exchange_rate=1200.0,
            ),
        )

        assert account.status == Account.STATUS.account_exchange_reg


class TestCurrencyExchangerForAccountNormalWithKB:
    VENDOR_CODE = "kb"

    def test_process_normal_with_exchangeable_amount(
        self, mocker: MockerFixture
    ) -> None:
        """환전 가능 금액 보유, 정상 처리"""

        mocker.patch.object(
            KBExchangeAPI,
            f"get_exchangeable_currencies",
            return_value=KBExchangeAPIResultFromGetExchangeableCurrencies(
                {
                    "apply_exchange_rate": 1200.0,
                    "currencies": [
                        {
                            "currency_code": "USD",
                            "exchange_possible_amt": 1000.0,
                        },
                    ],
                }
            ),
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            return_value=KBExchangeAPIResultFromConvertUSDToKRW(
                {
                    "apply_exchange_rate": 1200.0,
                    "exchange_possible_amt": 20.0,
                    "req_amt": 20.0,
                    "exchange_amt": 24000.0,
                }
            ),
        )

        account = create_account_etf_normal(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountNormal(account)
        result = manager.process()

        assert result.data == {
            "account_alias": account.account_alias,
            "exchange_rate": 1200.0,
            "exchangeable_amount": 20.0,
            "requested_amount": 20.0,
            "exchanged_amount": 24000.0,
        }

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_called_once_with(
            account,
            ForeignCurrency(
                currency_code="USD",
                exchange_amount=1000.0,
                exchange_rate=1200.0,
            ),
        )

        assert account.status == Account.STATUS.normal

    def test_process_normal_with_unexchangeable_amount(
        self, mocker: MockerFixture
    ) -> None:
        """환전 가능 금액 미보유, 정상 처리"""

        mocker.patch.object(
            KBExchangeAPI,
            "get_exchangeable_currencies",
            return_value=KBExchangeAPIResultFromGetExchangeableCurrencies(
                {
                    "apply_exchange_rate": 1200.0,
                    "currencies": [
                        {
                            "currency_code": "USD",
                            "exchange_possible_amt": 0.0,
                        },
                    ],
                }
            ),
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            return_value=KBExchangeAPIResultFromConvertUSDToKRW({}),
        )

        account = create_account_etf_normal(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountNormal(account)
        result = manager.process()

        assert result.data == {"account_alias": "20210516024403116595"}

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_not_called()

        assert account.status == Account.STATUS.normal

    def test_process_normal_with_no_exchangeable_currencies(
        self, mocker: MockerFixture
    ) -> None:
        """환전 가능 currency 미보유, 정상 처리"""

        mocker.patch.object(
            KBExchangeAPI,
            "get_exchangeable_currencies",
            return_value=KBExchangeAPIResultFromGetExchangeableCurrencies(
                {
                    "apply_exchange_rate": 1200.0,
                    "currencies": [
                        {
                            "currency_code": "KRW",
                            "exchange_possible_amt": 967473.0,
                        },
                    ],
                }
            ),
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            return_value=KBExchangeAPIResultFromConvertUSDToKRW({}),
        )

        account = create_account_etf_normal(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountNormal(account)
        with pytest.raises(PreconditionFailed) as e:
            manager.process()

        assert str(e.value) == "No exchangeable currencies"

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_not_called()

        assert account.status == Account.STATUS.normal

    def test_process_error_from_get_exchangeable_currencies(
        self, mocker: MockerFixture
    ) -> None:
        """환전 가능 금액 보유 무관, [TR API] 환전 가능 금액 조회 → HTTPError"""

        mocker.patch.object(
            KBExchangeAPI,
            "get_exchangeable_currencies",
            side_effect=requests.exceptions.HTTPError,
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            return_value=KBExchangeAPIResultFromConvertUSDToKRW({}),
        )

        account = create_account_etf_normal(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountNormal(account)
        with pytest.raises(requests.exceptions.HTTPError):
            manager.process()

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_not_called()

        assert account.status == Account.STATUS.normal

    def test_process_error_from_convert_usd_to_krw(self, mocker: MockerFixture) -> None:
        """환전 가능 금액 보유, [TR API] 환전 신청 → HTTPError"""

        mocker.patch.object(
            KBExchangeAPI,
            "get_exchangeable_currencies",
            return_value=KBExchangeAPIResultFromGetExchangeableCurrencies(
                {
                    "apply_exchange_rate": 1200.0,
                    "currencies": [
                        {
                            "currency_code": "USD",
                            "exchange_possible_amt": 1000.0,
                        },
                    ],
                }
            ),
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            side_effect=requests.exceptions.HTTPError,
        )

        account = create_account_etf_normal(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountNormal(account)
        with pytest.raises(requests.exceptions.HTTPError):
            manager.process()

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_called_once_with(account)
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_called_once_with(
            account,
            ForeignCurrency(
                currency_code="USD",
                exchange_amount=1000.0,
                exchange_rate=1200.0,
            ),
        )

        assert account.status == Account.STATUS.normal

    @pytest.mark.parametrize(
        "first_side_effect_for_convert_usd_to_krw",
        [
            KBExchangeAPIResultFromConvertUSDToKRW(
                {
                    "tr_code": "SWAM2224",
                    "account": "32330401401",
                    "status": "TRANSMIT_ERROR",
                    "msg_code": "I698",
                    "msg": "조회시점과 환전처리시점 환율이 다릅니다.다시 처리하시기 바랍니다.",
                }
            ),
        ],
    )
    def test_process_normal_with_exchangeable_amount_retry(
        self,
        mocker: MockerFixture,
        first_side_effect_for_convert_usd_to_krw: KBExchangeAPIResultFromConvertUSDToKRW,
    ) -> None:
        """환전 가능 금액 보유, 정상 처리, 재시도 가능한 오류 발생 시 재시도"""

        mocker.patch.object(
            KBExchangeAPI,
            f"get_exchangeable_currencies",
            return_value=KBExchangeAPIResultFromGetExchangeableCurrencies(
                {
                    "apply_exchange_rate": 1200.0,
                    "currencies": [
                        {
                            "currency_code": "USD",
                            "exchange_possible_amt": 1000.0,
                        },
                    ],
                }
            ),
        )
        mocker.patch.object(
            KBExchangeAPI,
            "convert_usd_to_krw",
            side_effect=[
                first_side_effect_for_convert_usd_to_krw,
                KBExchangeAPIResultFromConvertUSDToKRW(
                    {
                        "apply_exchange_rate": 1200.0,
                        "exchange_possible_amt": 20.0,
                        "req_amt": 20.0,
                        "exchange_amt": 24000.0,
                    }
                ),
            ],
        )

        account = create_account_etf_normal(self.VENDOR_CODE)

        manager = CurrencyExchangerForAccountNormal(account)
        result = manager.process()

        assert result.data == {
            "account_alias": account.account_alias,
            "exchange_rate": 1200.0,
            "exchangeable_amount": 20.0,
            "requested_amount": 20.0,
            "exchanged_amount": 24000.0,
        }

        account = Account.objects.get(account_alias=account.account_alias)

        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).get_exchangeable_currencies.assert_has_calls([call(account)] * 2)

        usd_currency = ForeignCurrency(
            currency_code="USD",
            exchange_amount=1000.0,
            exchange_rate=1200.0,
        )
        manager.get_api_by_vendor_code(
            self.VENDOR_CODE
        ).convert_usd_to_krw.assert_has_calls([call(account, usd_currency)] * 2)

        assert account.status == Account.STATUS.normal
