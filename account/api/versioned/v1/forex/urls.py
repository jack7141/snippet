from common.routers import CustomSimpleRouter
from .views import (
    ExchangeRateViewSet
)

router = CustomSimpleRouter(trailing_slash=False)
router.register(r'currency', ExchangeRateViewSet)

urlpatterns = router.urls + [

]
