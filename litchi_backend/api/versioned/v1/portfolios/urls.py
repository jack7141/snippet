from django.conf.urls import url
from .views import (
    PortfolioViewSet,
    PortfolioGuestViewSet,
    MarketIndexViewSet,
    MarketIndexTradingViewSet,
    MockInvestmentViewSet
)

urlpatterns = [
    url(r'^$', PortfolioViewSet.as_view({'get': 'retrieve'})),
    url(r'^guest$', PortfolioGuestViewSet.as_view({'get': 'retrieve'})),
    url(r'market_indexes$', MarketIndexViewSet.as_view({'get': 'list'})),
    url(r'market_indexes/tradings$', MarketIndexTradingViewSet.as_view({'get': 'list'})),
    url(r'mock_investments$', MockInvestmentViewSet.as_view({'get': 'retrieve'}))
]
