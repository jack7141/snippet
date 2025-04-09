from datetime import datetime, time

import pytz
from django.utils import timezone

KST_TZ = pytz.timezone('Asia/Seoul')

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
            if hasattr(value, 'keys'):
                value = DotDict(value)
            self[key] = value


def get_local_today():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def get_us_today_as_kst():
    us_today = get_us_today()
    us_date_as_kst = datetime.combine(date=us_today, time=time())
    return timezone.make_aware(us_date_as_kst, pytz.timezone("Asia/Seoul"))


def get_us_today():
    return datetime.now(tz=pytz.timezone('EST5EDT'))


def get_datetime_kst(dt: datetime):
    return dt.astimezone(KST_TZ)


def convert_datetime_kst(dt, dt_format='%Y-%m-%d'):
    if isinstance(dt, str):
        dt = datetime.strptime(dt, dt_format)

    if isinstance(dt, datetime):
        dt = get_datetime_kst(dt)
    return dt


def generate_choice_description(prefix, choice):
    return prefix + '(' + ', '.join([f"{k}: {v}" for k, v in choice._display_map.items()]) + ')'


# shortcut
gen_choice_desc = generate_choice_description
