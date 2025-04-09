from api.bases.orders.models import Event, OrderSetting
from rest_framework import serializers


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = "__all__"

    portfolio_id = serializers.CharField(help_text="포트폴리오 ID")


class OrderSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderSetting
        fields = "__all__"
