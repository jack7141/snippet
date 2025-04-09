import datetime
import logging

import pandas as pd
from celery import shared_task
from django.utils import timezone

from api.bases.forex.models import ExchangeRate

logger = logging.getLogger('django.server')

MIN_DATE = datetime.datetime(year=2020, month=10, day=13).date()


@shared_task(bind=True)
def register_exchange_rate(self, currency_code='USD', *args, **kwargs):
    logger.info("TRY register exchange rate")
    yesterday = timezone.localtime() - datetime.timedelta(days=1)

    if ExchangeRate.objects.exists():
        last_instance = ExchangeRate.objects.latest('base_date')
        start_date = last_instance.base_date + datetime.timedelta(days=1)
    else:
        start_date = MIN_DATE

    instances = []
    for _dt in pd.date_range(start=start_date, end=yesterday.date()):
        try:
            _instance = ExchangeRate.init_by_tr_response(currency_code=currency_code, base_date=_dt.date())
            if _instance.open and _instance.close:
                instances.append(_instance)
        except Exception as e:
            logger.warning(f"Fail register exchange rate for {_dt.date()}, detail: {e}")

    if instances:
        ExchangeRate.objects.bulk_create(instances)
        logger.info(f"DONE register exchange rate {start_date}-{yesterday}")
    else:
        logger.info("No exchange rate to register")
