from django.db.models.query import QuerySet

from api.bases.accounts.models import Account


def get_accounts_being_closed_etf(vendor_code: str) -> QuerySet:
    """환전 대상 계좌(해지 매도 완료, 환전 진행 중, 환전 실패, 해외 ETF 계좌)"""
    return Account.objects.filter(
        vendor_code=vendor_code,
        account_type__in=[Account.ACCOUNT_TYPE.etf],
        status__in=[
            Account.STATUS.account_sell_s,
            Account.STATUS.account_exchange_reg,
            Account.STATUS.account_exchange_f1,
        ],
    )


def get_accounts_normal_etf(vendor_code: str) -> QuerySet:
    """환전 대상 계좌(정상, 해외 ETF 계좌)"""
    return Account.objects.filter(
        vendor_code=vendor_code,
        account_type__in=[Account.ACCOUNT_TYPE.etf],
        status__in=[Account.STATUS.normal],
    )
