import ast
import redis
from datetime import datetime
from django.db.models import F, Max
from quantbox.base.infomax.models import Master, Bid, Quote, ClosingPrice
from rest_framework.mixins import ListModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .serializers import (
    MasterSerializer,
    BidSerializer,
    QuoteSerializer,
    ClosingPriceSerializer,
)


PORTFOLIO_UNIVERSE = (
    "FPE",
    "IHF",
    "ITA",
    "IEF",
    "ACWI",
    "XLY",
    "EMQQ",
    "DBA",
    "SPY",
    "REZ",
    "LQD",
    "VWO",
    "XLC",
    "HYG",
)


class RedisCache(redis.StrictRedis):
    def set(self, name, value, ex=None, px=None, nx=False, xx=False, keepttl=False):
        if isinstance(value, dict):
            value = str(value)
        return super().set(
            name=name, value=value, ex=ex, px=px, nx=nx, xx=xx, keepttl=keepttl
        )

    def get(self, name) -> dict or str:
        value = super().get(name=name)
        if isinstance(value, bytes):
            value = value.decode()
        try:
            value = ast.literal_eval(value)
            return value
        except ValueError:
            return value


class MasterViewSet(ListModelMixin, GenericViewSet):
    serializer_class = MasterSerializer
    queryset = Master.objects.all()

    def get_queryset(self):
        (last_date,) = self.queryset.values_list("base_date").latest("base_date")
        return self.queryset.filter(symbol__in=PORTFOLIO_UNIVERSE, base_date=last_date)


class BidViewSet(ListModelMixin, GenericViewSet):
    serializer_class = BidSerializer
    queryset = Bid.objects.all().order_by("-timestamp")

    def get_queryset(self):
        # last_date, = self.queryset.values_list('timestamp').latest('timestamp')
        return (
            self.queryset.values("symbol")
            .annotate(
                latest_date=Max("timestamp"),
                bid=F("bid"),
                ask=F("ask"),
                bid_size=F("bid_size"),
                ask_size=F("ask_size"),
                timestamp=F("timestamp"),
            )
            .values(
                "symbol",
                "bid",
                "ask",
                "bid_size",
                "ask_size",
                "latest_date",
                "timestamp",
            )
            .filter(symbol__in=PORTFOLIO_UNIVERSE, latest_date=F("latest_date"))
            .order_by("latest_date")
        )

    def list(self, request, *args, **kwargs):
        cache = RedisCache(host="localhost", db=2)
        results = []
        missed = []
        for _symbol in PORTFOLIO_UNIVERSE:
            cached = cache.get(f"2|{_symbol}")
            if cached:
                timestamp = datetime.combine(
                    date=datetime.strptime(cached["kor_date"], "%Y%m%d").date(),
                    time=datetime.strptime(cached["kor_time"], "%H%M%S").time(),
                )
                cached["timestamp"] = timestamp
                results.append(cached)
            else:
                missed.append(_symbol)

        serializer = self.get_serializer(data=results, many=True)
        serializer.is_valid()
        response = {"assets": serializer.data, "missed": missed}
        return Response(response)


class QuoteViewSet(ListModelMixin, GenericViewSet):
    serializer_class = QuoteSerializer
    queryset = Quote.objects.filter(timestamp__date="2020-11-12").order_by("-timestamp")

    def list(self, request, *args, **kwargs):
        cache = RedisCache(host="localhost", db=2)
        results = []
        missed = []

        for _symbol in PORTFOLIO_UNIVERSE:
            cached = cache.get(f"1|{_symbol}")
            if cached:
                timestamp = datetime.combine(
                    date=datetime.strptime(cached["kor_date"], "%Y%m%d").date(),
                    time=datetime.strptime(cached["kor_time"], "%H%M%S").time(),
                )
                cached["timestamp"] = timestamp
                results.append(cached)
            else:
                missed.append(_symbol)

        serializer = self.get_serializer(data=results, many=True)
        serializer.is_valid()

        response = {"assets": serializer.data, "missed": missed}
        return Response(response)


class ClosingPriceViewSet(ListModelMixin, GenericViewSet):
    serializer_class = ClosingPriceSerializer
    queryset = ClosingPrice.objects.all().order_by("-timestamp")

    def get_queryset(self):
        queryset = super().get_queryset()
        (last_date,) = queryset.values_list("busi_date").latest("busi_date")
        return queryset.filter(busi_date=last_date)

    def list(self, request, *args, **kwargs):
        return super().list(request=request, *args, **kwargs)
