import logging

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from django.conf import settings

from rest_framework import status
from memoize import memoize

from .constants import RETRYABLE_HTTP_STATUSES, HTTPRequestVerb
from .exceptions import PortfolioServiceRetryableHTTPError, PortfolioDoesNotExistError

logger = logging.getLogger(__name__)


class PortfolioService:
    HOST = settings.LITCHI_BACKEND.API_HOST
    TOKEN = settings.LITCHI_BACKEND.API_TOKEN
    TIMEOUT = settings.LITCHI_BACKEND.TIMEOUT
    TOKEN_PREFIX = "Token"
    PATHS = {"portfolios": "/api/v1/portfolios"}

    RETRY_STOP_AFTER_ATTEMPT = 10
    RETRY_WAIT_EXPONENTIAL_MULTIPLIER = 1
    RETRY_WAIT_EXPONENTIAL_MIN = 1
    RETRY_WAIT_EXPONENTIAL_MAX = 20

    CACHE_TIMEOUT = 300

    @classmethod
    def get_uri_by_function_name(cls, function_name):
        return f"{cls.HOST}{cls.PATHS[function_name]}"

    @classmethod
    @memoize(timeout=CACHE_TIMEOUT)
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        reraise=True,
        retry=(
            retry_if_exception_type(PortfolioServiceRetryableHTTPError)
            | retry_if_exception_type(requests.exceptions.Timeout)
            | retry_if_exception_type(requests.exceptions.ConnectionError)
        ),
        wait=wait_exponential(
            multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER,
            min=RETRY_WAIT_EXPONENTIAL_MIN,
            max=RETRY_WAIT_EXPONENTIAL_MAX,
        ),
    )
    def request(cls, verb, *args, **kwargs):
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"{cls.TOKEN_PREFIX} {cls.TOKEN}"
        kwargs["headers"] = headers
        kwargs["timeout"] = cls.TIMEOUT

        logger.debug(f"""verb: {verb}, args: {args}, kwargs: {kwargs}""")

        r = requests.request(verb, *args, **kwargs)
        if r.status_code in RETRYABLE_HTTP_STATUSES:
            raise PortfolioServiceRetryableHTTPError(f"HTTP Error {r.status_code}")
        if r.status_code == status.HTTP_404_NOT_FOUND:
            raise PortfolioDoesNotExistError
        r.raise_for_status()
        return r.json()

    @classmethod
    def get(cls, **kwargs):
        """Get portfolio sequences

        :param universe_index: Universe index
        :type universe_index: int
        :param strategy_code: Strategy code
        :type strategy_code: int
        :param port_date: Portfolio date
        :type port_date: str, "YYYY-MM-DD"
        :returns: Portfolio data
          example:
          {
           'date': '2021-05-18',
           'universe_index': 1080,
           'portfolios':
            [
             {'port_seq': '20210518108000002',
              'risk_type': 0,
              'risk_name': '초저위험',
              'port_data':
               [
                {'code': 'SCHP',
                 'weight': 0.3,
                 'asset_category': '채권'
                }
               ]
             }
            ]
          }
        :rtype: dict
        """
        return cls.request(
            HTTPRequestVerb.GET,
            url=cls.get_uri_by_function_name("portfolios"),
            params=kwargs,
        )
