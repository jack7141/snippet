from rest_framework.serializers import ModelSerializer

from api.bases.infomax.models import Master, Bid, Quote, ClosingPrice


class MasterSerializer(ModelSerializer):
    class Meta:
        model = Master
        fields = '__all__'


class BidSerializer(ModelSerializer):
    class Meta:
        model = Bid
        fields = ['symbol', 'bid_size', 'ask_size',
                  'bid', 'ask',
                  'tot_bid_size', 'tot_ask_size',
                  'timestamp']


class QuoteSerializer(ModelSerializer):
    class Meta:
        model = Quote
        fields = '__all__'


class ClosingPriceSerializer(ModelSerializer):
    class Meta:
        model = ClosingPrice
        fields = ['busi_date', 'symbol', 'last', 'timestamp']
