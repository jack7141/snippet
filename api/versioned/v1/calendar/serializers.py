from rest_framework import serializers
from api.bases.funds.models import *


class CalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calendar
        fields = ('date', 'day_code', 'is_holiday', 'day_name',)
