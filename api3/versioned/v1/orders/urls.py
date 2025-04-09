from common.routers import CustomSimpleRouter

from .views import (
    OrderViewSet,
    OrderDetailViewSet
)

router = CustomSimpleRouter(trailing_slash=False)
router.register(r'', OrderViewSet)
router.register(r'details', OrderDetailViewSet)

urlpatterns = [
]

urlpatterns += router.urls
