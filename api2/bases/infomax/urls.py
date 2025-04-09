from django.contrib import admin
from django.urls import path, include

from .views import (
    MasterViewSet,
    BidViewSet,
    QuoteViewSet,
    ClosingPriceViewSet,
    RandomQuoteViewSet,
)

urlpatterns = [
    path("master", MasterViewSet.as_view({"get": "list"})),
    path("bid", BidViewSet.as_view({"get": "list"})),
    path("quote", QuoteViewSet.as_view({"get": "list"})),
    path("close", ClosingPriceViewSet.as_view({"get": "list"})),
]
