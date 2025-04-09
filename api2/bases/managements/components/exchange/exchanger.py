from abc import ABC, abstractstaticmethod, abstractmethod
from contextlib import contextmanager
import logging

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from django.conf import settings

from api.bases.accounts.models import Account
from api.bases.managements.components.exchange.currencies import ForeignCurrency
from api.bases.managements.components.exchange.apis import (
    EXCHANGE_API_BY_VENDOR_CODE,
    AbstractExchangeAPI,
)
from api.bases.managements.components.exchange.results import (
    AbstractAPIResultFromConvertUSDToKRW,
    CurrencyExchangerResult,
    CurrencyExchangerResultForNotExchangeable,
    CurrencyExchangerResultForCompleted,
    APIResultFailureRetryableError,
)
from common.exceptions import PreconditionFailed

logger = logging.getLogger(__name__)

TR_BACKEND = settings.TR_BACKEND


class CurrencyExchangerError(Exception):
    pass


class NotExchangeableError(CurrencyExchangerError):
    pass


class WrongTargetError(CurrencyExchangerError):
    pass


class AbstractCurrencyExchanger(ABC):
    """환전 처리"""

    RETRY_STOP_AFTER_ATTEMPT = 3
    RETRY_WAIT_EXPONENTIAL_MULTIPLIER = 1
    RETRY_WAIT_EXPONENTIAL_MIN = 1
    RETRY_WAIT_EXPONENTIAL_MAX = 20

    def __init__(self, account: Account) -> None:
        self.account = account

    def get_api_by_vendor_code(self, vendor_code: str) -> AbstractExchangeAPI:
        return EXCHANGE_API_BY_VENDOR_CODE[vendor_code]

    def process(self) -> CurrencyExchangerResult:
        self._validate_account(self.account)
        return self.process_exchange(self.account)

    @abstractstaticmethod
    def _validate_account(account: Account) -> None:
        pass

    def process_exchange(self, account: Account) -> CurrencyExchangerResult:
        with self._process_exchange_contextmanager(account):
            return self.exchange_if_possible_with_retry(account)

    @contextmanager
    def _process_exchange_contextmanager(self, account: Account) -> None:
        yield

    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        reraise=True,
        retry=retry_if_exception_type(APIResultFailureRetryableError),
        wait=wait_exponential(
            multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER,
            min=RETRY_WAIT_EXPONENTIAL_MIN,
            max=RETRY_WAIT_EXPONENTIAL_MAX,
        ),
    )
    def exchange_if_possible_with_retry(
        self, account: Account
    ) -> CurrencyExchangerResult:
        return self.exchange_if_possible(account)

    @abstractmethod
    def exchange_if_possible(self, account: Account) -> CurrencyExchangerResult:
        # Call self.get_exchangeable, self.exchange here.
        pass

    def get_exchangeable(self, account: Account) -> ForeignCurrency:
        """환전 가능 금액 조회"""

        # TODO: 현재 USD만 환전, 기타 외화 처리 확인 필요.
        USD = "USD"

        result = self.get_api_by_vendor_code(
            account.vendor_code
        ).get_exchangeable_currencies(account)
        result.raise_if_failed()

        if USD not in result.currency_map:
            raise PreconditionFailed("No exchangeable currencies")

        return result.currency_map[USD]

    @staticmethod
    def _validate_if_exchangeable(currency: ForeignCurrency) -> None:
        """환전 가능 금액 보유 중인지 검증"""

        if currency.is_empty or currency.exchange_amount < 0:
            raise NotExchangeableError

    def exchange(
        self, account: Account, usd_currency: ForeignCurrency
    ) -> AbstractAPIResultFromConvertUSDToKRW:
        """환전 신청"""

        with self._exchange_contextmanager(account):
            try:
                result = self.get_api_by_vendor_code(
                    account.vendor_code
                ).convert_usd_to_krw(account, usd_currency)
                logger.debug(f"Response from exchange API: {result.data}")
            except Exception as e:
                logger.warning("Error from exchange API", exc_info=True)
                raise e

            return result

    @contextmanager
    def _exchange_contextmanager(self, account: Account) -> None:
        yield

    @staticmethod
    def _get_log_message_for_not_exchangeable(header: str, account: Account) -> str:
        return f"[환전]{header} Account {account.account_alias} - 환전 가능 금액 미보유"

    @staticmethod
    def _get_log_message_for_completed(
        header: str, account: Account, result: AbstractAPIResultFromConvertUSDToKRW
    ) -> str:
        return (
            f"[환전]{header} Account {account.account_alias} - "
            f"환율 {result.exchange_rate}, ${result.requested_amount:,} → {result.exchanged_amount:,}원"
        )


class CurrencyExchangerForAccountBeingClosed(AbstractCurrencyExchanger):
    """환전 처리 - 해지 매도 대상 계좌"""

    @staticmethod
    def _validate_account(account: Account) -> None:
        """환전 대상 계좌(해지 매도 완료, 환전 진행 중, 환전 실패, 해외 ETF 계좌) 검증"""
        if account.account_type != Account.ACCOUNT_TYPE.etf:
            raise WrongTargetError

        if account.status not in [
            Account.STATUS.account_sell_s,
            Account.STATUS.account_exchange_reg,
            Account.STATUS.account_exchange_f1,
        ]:
            raise WrongTargetError

    @contextmanager
    def _process_exchange_contextmanager(self, account: Account) -> None:
        previous_account_status = account.status
        try:
            yield
        finally:
            self.save_account(account, previous_account_status)

    def exchange_if_possible(self, account: Account) -> CurrencyExchangerResult:
        """환전 처리

        환전 가능 금액 미보유 시 → account.status 변경 후 종료
        환전 가능 금액 보유 시 → 환전 신청
        """
        # 환전 가능 금액 조회
        usd_currency = self.get_exchangeable(account)

        # 환전 가능 금액 미보유 시 account.status 변경 후 종료
        try:
            self._validate_if_exchangeable(usd_currency)
        except NotExchangeableError:
            self._set_account_status_by_currency_if_not_exchangeable(
                account, usd_currency
            )
            logger.info(
                self._get_log_message_for_not_exchangeable("[해지 매도 계좌][미대상]", account)
            )
            return CurrencyExchangerResultForNotExchangeable(account)

        # 환전 신청
        result = self.exchange(account, usd_currency)
        result.raise_if_failed()

        logger.info(
            self._get_log_message_for_completed("[해지 매도 계좌][완료]", account, result)
        )
        return CurrencyExchangerResultForCompleted(account, result)

    @staticmethod
    def _set_account_status_by_currency_if_not_exchangeable(
        account: Account, currency: ForeignCurrency
    ) -> None:
        """환전 가능 금액 미보유 시 account.status 변경"""

        if currency.is_empty:
            account.status = Account.STATUS.account_exchange_s
        elif currency.exchange_amount < 0:
            account.status = Account.STATUS.account_exchange_f1

    @staticmethod
    def save_account(account: Account, previous_account_status: int) -> None:
        logger.info(
            f"UPDATE Account({account.account_alias}) status {previous_account_status}->{account.status}"
        )
        account.save()

    @contextmanager
    def _exchange_contextmanager(self, account: Account) -> None:
        """환전 신청 전후 account.status 업데이트"""

        account.update_status(Account.STATUS.account_exchange_reg)
        yield
        account.status = Account.STATUS.account_exchange_s


class CurrencyExchangerForAccountNormal(AbstractCurrencyExchanger):
    """환전 처리 - 정상 계좌"""

    @staticmethod
    def _validate_account(account: Account) -> None:
        """환전 대상 계좌(정상, 해외 ETF 계좌) 검증"""
        if account.account_type != Account.ACCOUNT_TYPE.etf:
            raise WrongTargetError

        if account.status != Account.STATUS.normal:
            raise WrongTargetError

    def exchange_if_possible(self, account: Account) -> CurrencyExchangerResult:
        """환전 처리

        환전 가능 금액 미보유 시 → 종료
        환전 가능 금액 보유 시 → 환전 신청
        """
        # 환전 가능 금액 조회
        usd_currency = self.get_exchangeable(account)

        # 환전 가능 금액 미보유 시 종료
        try:
            self._validate_if_exchangeable(usd_currency)
        except NotExchangeableError:
            logger.info(
                self._get_log_message_for_not_exchangeable("[정상 계좌][미대상]", account)
            )
            return CurrencyExchangerResultForNotExchangeable(account)

        # 환전 신청
        result = self.exchange(account, usd_currency)
        result.raise_if_failed()

        logger.info(self._get_log_message_for_completed("[정상 계좌][완료]", account, result))
        return CurrencyExchangerResultForCompleted(account, result)
