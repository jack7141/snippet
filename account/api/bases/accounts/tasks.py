import logging

from celery import shared_task
from django.utils import timezone

from api.bases.accounts.models import Account, SumUp, Trade
from api.versioned.v1.accounts.serializers import (
    AmountHistoryCreateSerializer, AmountHistoryUpdateSerializer, HoldingCreateSerializer
)
from common.exceptions import PreconditionFailed, DuplicateAccess
from common.utils import get_datetime_kst

logger = logging.getLogger('django.server')


@shared_task(bind=True)
def settle_daily_amount(*args, **kwargs):
    logger.info("RUN TASK")
    for acct in Account.objects.filter(trade__isnull=False).distinct():
        serializer = AmountHistoryCreateSerializer(data={'account_alias': acct.pk})
        try:
            if serializer.is_valid():
                serializer.save()
        except Exception as e:
            logger.warning(e)
    logger.info("DONE TASK")


@shared_task(bind=True)
def register_sum_up(*args, **kwargs):
    logger.info("TRY REGISTER SUM_UP")

    unclassified_trade_set = Trade.objects.exclude(j_name__in=SumUp.objects.values_list('j_name', flat=True))

    sum_up_candidates = []
    for j_info in unclassified_trade_set.values('j_name', 'j_code').distinct():
        sum_up_candidates.append(SumUp(**j_info))

    created = SumUp.objects.bulk_create(sum_up_candidates)
    logger.info(f"REGISTERED SUM_UP({len(created)})")
    return {"created": len(created)}


@shared_task(bind=True)
def recalculate_amount(self, account_alias_whitelist=None, j_names=None, *args, **kwargs):
    logger.info(f"TRY recalculate DailyAmount, J_NAMES: {j_names}")
    self.update_state(state="PROGRESS")
    queryset = Account.objects.filter(trade__j_name__in=j_names, amounthistory__isnull=False).distinct()

    if account_alias_whitelist:
        logger.info(f"target AliasSet: {account_alias_whitelist}")
        queryset = queryset.filter(account_alias__in=account_alias_whitelist)

    updated_accounts, updated_rows = 0, 0
    for acct in queryset.iterator():
        diffs = AmountHistoryUpdateSerializer.get_diffs(acct=acct, queryset=acct.amounthistory_set)

        if not diffs.empty:
            updated_accounts += 1
            for i, row in diffs.iterrows():
                instance = acct.amounthistory_set.get(created_at=get_datetime_kst(i))
                serializer = AmountHistoryUpdateSerializer(instance, data=row.to_dict())
                serializer.is_valid(raise_exception=True)
                serializer.save()
                updated_rows += 1

    result = {'updated_accounts': updated_accounts, 'updated_rows': updated_rows,
              'j_names': j_names, 'account_alias_whitelist': account_alias_whitelist}
    logger.info("Recalculated DailyAmount")
    return result


@shared_task(bind=Trade)
def calculate_holdings(self, *args, **kwargs):
    today = timezone.now()
    registered_alias_set = Account.objects.filter(
        holding__created_at__date=today).distinct().values_list('account_alias', flat=True)
    queryset = Account.objects.exclude(status=0, account_alias__in=registered_alias_set)

    j_name_map = SumUp.get_trade_types(SumUp.objects.filter(trade_type__in=['BID', 'ASK', 'IMPORT', 'EXPORT']))

    results = {
        'trial': 0,
        'success': 0,
        'skipped': 0,
        'fail': 0
    }

    for acct in queryset.iterator():
        s = HoldingCreateSerializer(data={'account_alias': acct.account_alias, 'to_date': today.date(),
                                          'j_name_map': j_name_map})

        results['trial'] += 1
        if s.is_valid():
            try:
                s.save()
                results['success'] += 1
            except PreconditionFailed as e:
                results['skipped'] += 1
            except DuplicateAccess as e:
                results['skipped'] += 1
            except Exception as e:
                logger.warning(f"Failed to calc qty for {acct.account_alias}, detail: {e}")
                results['fail'] += 1

    return results
