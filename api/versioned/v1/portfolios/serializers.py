import json
import pandas as pd
import numpy as np
from rest_framework import serializers

from api.bases.portfolios.models import PortfolioDaily
from api.bases.etf_us.models import MarketIndex


class PortfolioSerializer(serializers.ModelSerializer):
    port_seq = serializers.CharField(help_text='포트폴리오 시퀀스 번호')
    risk_type = serializers.IntegerField(source='port_type.risk_type', help_text='위험도 종류')
    risk_name = serializers.CharField(source='port_type.risk_name', help_text='위험도 명')
    port_data = serializers.ListField(help_text='포트폴리오')
    universe_index = serializers.SlugRelatedField(
        source='port_type.universe_index',
        slug_field='universe_index',
        read_only=True,
        help_text='유니버스 구분'
    )

    class Meta:
        model = PortfolioDaily
        exclude = ('port_date', 'update_date', 'description', 'universe_index', 'bw_type', 'port_type')


class PortfolioWrapSerializer(serializers.Serializer):
    class PortfolioDataSerializer(serializers.ModelSerializer):
        port_seq = serializers.CharField(help_text='포트폴리오 시퀀스 번호')
        risk_type = serializers.IntegerField(source='port_type.risk_type', help_text='위험도 종류')
        risk_name = serializers.CharField(source='port_type.risk_name', help_text='위험도 명')
        port_data = serializers.ListField(help_text='포트폴리오')
        description = serializers.ListField(source='description_list', help_text='포트폴리오 간이 설명')
        universe_index = serializers.SlugRelatedField(
            source='port_type.universe_index',
            slug_field='universe_index',
            read_only=True,
            help_text='유니버스 구분'
        )

        class Meta:
            model = PortfolioDaily
            exclude = ('port_date', 'update_date', 'universe_index', 'bw_type', 'port_type')

    date = serializers.DateField(help_text='포트폴리오 생성일')
    universe_index = serializers.IntegerField(help_text='유니버스 구분')
    portfolios = PortfolioDataSerializer(many=True, help_text='포트폴리오 목록')


class PortfolioForGuestSerializer(serializers.ModelSerializer):
    port_seq = serializers.CharField(help_text='포트폴리오 시퀀스 번호')
    risk_type = serializers.IntegerField(source='port_type.risk_type', help_text='위험도 종류')
    risk_name = serializers.CharField(source='port_type.risk_name', help_text='위험도 명')
    port_data = serializers.ListField(help_text='포트폴리오')
    description = serializers.ListField(source='description_list', help_text='포트폴리오 간이 설명')
    universe_index = serializers.SlugRelatedField(
        source='port_type.universe_index',
        slug_field='universe_index',
        read_only=True,
        help_text='유니버스 구분'
    )
    port_data = serializers.SerializerMethodField(help_text='포트폴리오', read_only=True)

    class Meta:
        model = PortfolioDaily
        exclude = ('port_date', 'update_date', 'universe_index', 'bw_type', 'port_type')

    def get_port_data(self, instance):
        df = pd.DataFrame(instance.get_port_data())[['asset_category', 'weight']]

        if instance.universe_index == 1080:
            # 2021.06.29 - 글로벌 ETF(1080)의 경우 전체 자산군 합에서 7%를 유동성으로 처리하기로 함
            result = (df.groupby('asset_category').sum() * 0.93).reset_index().append(
                {'asset_category': 'LIQ', 'weight': 0.07}, ignore_index=True).to_json(orient='records')
        else:
            result = df.groupby('asset_category').sum().reset_index().to_json(orient='records')

        return json.loads(result)


class PortfolioForGuestWrapSerializer(serializers.Serializer):
    date = serializers.DateField(help_text='포트폴리오 생성일')
    universe_index = serializers.IntegerField(help_text='유니버스 구분')
    portfolios = PortfolioForGuestSerializer(many=True, help_text='포트폴리오 목록')


class MarketIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketIndex
        fields = ('symbol', 'name')


class MarketIndexTradingSerializer(serializers.ModelSerializer):
    tradings = serializers.SerializerMethodField()

    class Meta:
        model = MarketIndex
        fields = ('symbol', 'name', 'tradings')

    def get_tradings(self, obj):
        result = {}
        tradings = obj.get('tradings')

        if tradings is not None and tradings.exists():
            df = pd.DataFrame(tradings.values('date', 'price'))
            df['date'] = pd.to_datetime(df['date']).astype(np.int64) // 10 ** 6
            df = df.set_index('date')
            result = df.to_dict().get('price')

        return result


class MockInvestmentSerializer(serializers.Serializer):
    evaluation_amount = serializers.DictField(help_text="평가금액")

    class Meta:
        fields = ('evaluation_amount',)
