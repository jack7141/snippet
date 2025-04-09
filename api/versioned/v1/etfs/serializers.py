from rest_framework import serializers
from api.bases.etf_kr.models import *
from common.utils import get_serializer_class


class OperationListSerializer(serializers.ModelSerializer):
    asset_name = serializers.CharField(source='name')

    class Meta:
        model = Profile
        fields = ('isin', 'symbol', 'asset_name')


class OperationRetrieveSerializer(OperationListSerializer):
    trading = get_serializer_class(Trading)(many=True, read_only=True, source='get_month_ago_trading')

    class Meta:
        model = Profile
        fields = '__all__'


class TradingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trading
        fields = '__all__'
