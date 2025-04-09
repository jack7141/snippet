from datetime import datetime, time
from typing import Optional

import pytz
from django.utils import timezone
from django.db.models.query import QuerySet


class DotDict(dict):
    """
    a dictionary that supports dot notation
    as well as dictionary access notation
    usage: d = DotDict() or d = DotDict({'val1':'first'})
    set attributes: d.val2 = 'second' or d['val2'] = 'second'
    get attributes: d.val2 or d['val2']
    """

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def __init__(self, dct):
        for key, value in dct.items():
            if hasattr(value, "keys"):
                value = DotDict(value)
            self[key] = value


def get_local_today():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def get_us_today_as_kst():
    us_today = get_us_today()
    us_date_as_kst = datetime.combine(date=us_today, time=time())
    return timezone.make_aware(us_date_as_kst, pytz.timezone("Asia/Seoul"))


def get_us_today():
    return datetime.now(tz=pytz.timezone("EST5EDT"))


def generate_choice_description(prefix, choice):
    return (
        prefix
        + "("
        + ", ".join([f"{k}: {v}" for k, v in choice._display_map.items()])
        + ")"
    )


# shortcut
gen_choice_desc = generate_choice_description


def cast_str_to_int(value):
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise ValueError("Type of value must be str.")

    return int(value)


def convert_date_to_yyyy_mm_dd(date):
    return date.strftime("%Y-%m-%d")


def get_account_aliases_from_accounts(accounts: QuerySet) -> list[str]:
    return list(accounts.values_list("account_alias", flat=True))


def get_account_aliases_from_accounts_with_test_account_aliases(
    accounts: QuerySet, test_account_aliases: Optional[list[str]] = None
) -> list[str]:
    if test_account_aliases is not None:
        accounts = accounts.filter(account_alias__in=test_account_aliases)
    return get_account_aliases_from_accounts(accounts)
