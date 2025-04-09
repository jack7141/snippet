from rest_framework.routers import DefaultRouter

from .views import MasterViewSet, ClosingPriceViewSet

router = DefaultRouter()
router.register('master', MasterViewSet)
router.register('close', ClosingPriceViewSet)

urlpatterns = router.urls + [
]
