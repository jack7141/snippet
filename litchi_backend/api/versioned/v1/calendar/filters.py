import django_filters

from api.bases.funds.models import Calendar


class CalendarFilter(django_filters.FilterSet):
    class Meta:
        model = Calendar
        fields = ('date', 'day_code', 'is_holiday', 'day_name',)
