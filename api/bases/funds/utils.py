from pandas.tseries.offsets import CDay
from .models import Calendar


class HolidayOffset:
    HOLIDAYS = None

    def __new__(cls, *args, **kwargs):
        if not cls.HOLIDAYS:
            cls.HOLIDAYS = list(Calendar.objects.filter(
                is_holiday='Y'
            ).exclude(day_code__in=(1, 7)).values_list('date', flat=True))

        return CDay(*args, holidays=cls.HOLIDAYS)


BDay = HolidayOffset
