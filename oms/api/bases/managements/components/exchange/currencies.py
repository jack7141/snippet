from dataclasses import dataclass
import logging
import datetime
from typing import Optional

from memoize import memoize

from api.bases.core.requests_with_retry import get_requests_retry_session_with_logging
from common.utils import get_us_today

logger = logging.getLogger(__name__)


@dataclass
class ForeignCurrency:
    USD_CURRENCY_CODE = 0
    KRW2USD = 1
    USD2KRW = 2

    currency_code: str
    exchange_amount: float
    exchange_rate: float

    CACHE_TIMEOUT: int = 120

    @property
    def is_empty(self) -> bool:
        return self.exchange_amount == 0

    @staticmethod
    @memoize(timeout=CACHE_TIMEOUT)
    def get_exchange_rate(api_base: str, date: Optional[datetime.date] = None) -> float:
        if date is None:
            date = get_us_today().date()

        api_url = f"{api_base}/api/v1/kb/exchange/rate/{date.strftime('%Y%m%d')}"
        response = get_requests_retry_session_with_logging().get(api_url)

        response_data = response.json()
        currencies = response_data.get("currencies")
        if not currencies:
            raise ValueError(f"No data on {date}")

        return currencies[-1]["transaction"]
