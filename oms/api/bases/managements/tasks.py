import logging
from celery import shared_task
from django.conf import settings

from api.bases.managements.task_runners import (
    OrderAccountFetcher,
    ExecutionManagementRegister,
    ErrorAccountMonitor,
    SplitOrderController,
    CurrencyExchangerRunnerForAllAccountsBeingClosedWithVendor,
    CurrencyExchangerRunnerForAllAccountsNormalWithVendor,
)
from common.utils import cast_str_to_int

logger = logging.getLogger(__name__)
TR_BACKEND = settings.TR_BACKEND


@shared_task(bind=True, base=OrderAccountFetcher)
def order_account_selection(self, vendor_code=None, *args, **kwargs):
    try:
        return self.process(vendor_code=vendor_code, *args, **kwargs)
    except Exception as e:
        logger.error(str(e))


@shared_task(bind=True, base=ExecutionManagementRegister)
def execute_order_queues(
    self, position=None, vendor_code=None, sub_task_expires=1, *args, **kwargs
):
    try:
        return self.process(
            position=position,
            vendor_code=vendor_code,
            sub_task_expires=sub_task_expires,
            *args,
            **kwargs,
        )
    except Exception as e:
        logger.error(str(e))


@shared_task(bind=True, base=ExecutionManagementRegister)
def cancel_order_queues(self, position=None, vendor_code=None, *args, **kwargs):
    try:
        return self.cancel_unexecuted_orders(
            position=position, vendor_code=vendor_code, *args, **kwargs
        )
    except Exception as e:
        logger.error(str(e))


@shared_task(bind=True, base=ErrorAccountMonitor)
def error_account_monitor(self, monitor_dates=None, *args, **kwargs):
    try:
        return self.process(monitor_dates=monitor_dates, *args, **kwargs)
    except Exception as e:
        logger.error(str(e))


@shared_task(bind=True, base=SplitOrderController)
def execute_order_fount(
    self,
    vendor_code=None,
    time_schedule="full",
    min_qty=20,
    sub_task_expires=1,
    *args,
    **kwargs,
):
    sub_task_expires = cast_str_to_int(sub_task_expires)

    try:
        return self.executer(
            vendor_code, time_schedule, min_qty, sub_task_expires, *args, **kwargs
        )
    except Exception as e:
        logger.error(str(e))


# 환전
@shared_task(bind=True, base=CurrencyExchangerRunnerForAllAccountsBeingClosedWithVendor)
def exchange_accounts_being_closed(self, vendor_code=None, *args, **kwargs):
    """환전 실행 - 특정 증권사 전체 계좌(해지 매도 계좌)"""
    try:
        return self.process(vendor_code=vendor_code, *args, **kwargs)
    except Exception as e:
        logger.info(f"[환전][전체 해지 매도 계좌][오류] 증권사 {vendor_code} - {e}")
        raise e


@shared_task(bind=True, base=CurrencyExchangerRunnerForAllAccountsNormalWithVendor)
def exchange_accounts_normal(self, vendor_code=None, *args, **kwargs):
    """환전 실행 - 특정 증권사 전체 계좌(정상 계좌)"""
    try:
        return self.process(vendor_code=vendor_code, *args, **kwargs)
    except Exception as e:
        logger.info(f"[환전][전체 정상 계좌][오류] 증권사 {vendor_code} - {e}")
        raise e


# Testing
@shared_task
def test_error():
    1 / 0


@shared_task
def test_log_error():
    logger.error("Log error test")
