from rest_framework import serializers
from api.bases.funds.models import *
from django.db import connections
from common.utils import get_serializer_class


class OperationListSerializer(serializers.ModelSerializer):

    category_name = serializers.SlugRelatedField(
        source='category_code',
        slug_field='name',
        read_only=True
    )

    asset_category = serializers.SlugRelatedField(
        source='category_code.code',
        slug_field='asset_category',
        read_only=True
    )

    class Meta:
        model = Operation
        fields = ('symbol', 'name', 'category_name', 'asset_category',)


class OperationRetrieveSerializer(OperationListSerializer):
    company = get_serializer_class(Company)(source='company_code')
    fees = get_serializer_class(Fee)(many=True, read_only=True)
    processes = get_serializer_class(Process)(many=True, read_only=True)
    ratings = get_serializer_class(Rating)(many=True, read_only=True)
    redemption = get_serializer_class(Redemption)(many=True, read_only=True)
    styles = get_serializer_class(Style)(many=True, read_only=True, source='get_last_2_styles')
    terms = get_serializer_class(Terms)(many=True, read_only=True)
    trading = get_serializer_class(Trading)(many=True, read_only=True, source='get_month_ago_trading')
    families = serializers.SerializerMethodField()

    recent_holdings = get_serializer_class(Holding)(many=True, read_only=True, source='get_recent_holding')
    recent_performances = get_serializer_class(Performance)(many=True, read_only=True, source='get_recent_performance')
    recent_portfolio = get_serializer_class(Portfolio)(read_only=True, source='get_recent_portfolio')
    recent_returns = get_serializer_class(Returns)(many=True, read_only=True, source='get_recent_return')
    recent_sales = get_serializer_class(Sales)(many=True, read_only=True, source='get_recent_sale')
    recent_sectors = get_serializer_class(Sector)(many=True, read_only=True, source='get_recent_sector')

    analysis = serializers.SerializerMethodField()

    class Meta:
        model = Operation
        exclude = ['category_code', 'company_code', 'company_symbol', 'is_private', 'bm_code']

    def get_families(self, obj):
        queryset = Operation.objects \
            .values_list('symbol', 'name', 'fees__rate', 'fees__type_code', 'fees__group_code', 'trading__date',
                         'trading__aum') \
            .prefetch_related('fees', 'trading') \
            .filter(share_class_symbol=obj.share_class_symbol, end_date__isnull=True) \
            .extra(where=['Fee.Rate=(SELECT Max(Fee.Rate) FROM Fee WHERE Fee.Symbol=Operation.Symbol)']) \
            .extra(
            where=['Trading.AsOfDate = (SELECT Max(Trading.AsOfDate) FROM Trading WHERE Symbol=Operation.Symbol)']) \
            .order_by()
        return queryset

    def get_analysis(self, obj):
        tr, pr = None, None
        tr_filter = obj.terms_return.filter(term_type='M', term__in=[1, 3, 6])
        pr_filter = obj.performance.filter(term_type='M', term__in=[1, 3, 6])

        if tr_filter.exists():
            tr = tr_filter.order_by('term').latest('date')

        if pr_filter.exists():
            pr = pr_filter.order_by('term').latest('date')

        tr_serializer = get_serializer_class(TermsReturn)(tr)
        pr_serializer = get_serializer_class(Performance)(pr)

        merged_dict = dict(tr_serializer.data.items() | pr_serializer.data.items())

        filter_keys = [
            'term_return',
            'term_return_per_rank',
            'standard_deviation',
            'standard_deviation_per_rank',
            'shape_ratio',
            'shape_ratio_per_rank',
            'tracking_error',
            'tracking_error_per_rank',
            'information_ratio',
            'information_ratio_per_rank'
        ]

        return {k: v for k, v in merged_dict.items() if k in filter_keys}


class OperationTradingSerializer(serializers.ModelSerializer):
    # trading = get_serializer_class(Trading)(many=True, read_only=True, source='get_month_ago_trading')

    class Meta:
        model = Operation
        fields = ('symbol', 'name', 'trading')


class TradingSerializer(serializers.ModelSerializer):
    # company_name = serializers.CharField(source='company_code.name')
    # category_name = serializers.CharField(source='category_code.name')

    class Meta:
        model = Trading
        exclude = ['company_code', 'category_code', 'update_date', 'symbol']