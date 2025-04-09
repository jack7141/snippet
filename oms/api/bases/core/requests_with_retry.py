from typing import Optional, Callable

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from rest_framework import status

from api.bases.core.logging import log_response

# https://www.peterbe.com/plog/best-practice-with-retries-with-requests
# https://findwork.dev/blog/advanced-usage-python-requests-timeouts-retries-hooks/

DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 2
DEFAULT_STATUS_FORCELIST = (
    status.HTTP_429_TOO_MANY_REQUESTS,
    status.HTTP_500_INTERNAL_SERVER_ERROR,
    status.HTTP_502_BAD_GATEWAY,
    status.HTTP_503_SERVICE_UNAVAILABLE,
    status.HTTP_504_GATEWAY_TIMEOUT,
)


def get_requests_retry_session(
    retries: int = DEFAULT_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    status_forcelist: list[int] = DEFAULT_STATUS_FORCELIST,
    session: Optional[requests.Session] = None,
) -> requests.Session:
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_requests_retry_session_with_logging(
    retries: int = DEFAULT_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    status_forcelist: list[int] = DEFAULT_STATUS_FORCELIST,
    session: Optional[requests.Session] = None,
    logging_hook: Callable = log_response,
) -> requests.Session:
    session = get_requests_retry_session(
        retries, backoff_factor, status_forcelist, session
    )
    session.hooks["response"].append(logging_hook)
    return session
