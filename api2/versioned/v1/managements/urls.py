from .views import (
    OrderQueueViewSet,
    OrderBasketViewSet,
    OrderLogViewSet,
    SuspensionAccountViewSet,
    ErrorOccurViewSet,
)
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r"order_basket/(?P<mode>\w+)", OrderBasketViewSet)
router.register(r"queue", OrderQueueViewSet)
router.register(r"log", OrderLogViewSet)
router.register(r"abnormal", SuspensionAccountViewSet)
router.register(r"error_account", ErrorOccurViewSet)

urlpatterns = [] + router.urls
