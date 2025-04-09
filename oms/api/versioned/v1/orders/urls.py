from .views import EventViewSet, OrderSettingViewSet
from rest_framework.routers import DefaultRouter


router = DefaultRouter()

router.register(r"event", EventViewSet)
router.register(r"setting", OrderSettingViewSet)


urlpatterns = [] + router.urls
