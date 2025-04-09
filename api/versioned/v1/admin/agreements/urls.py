from api.versioned.v1.admin.agreements.views import TypeViewSet, AgreementViewSet

from rest_framework import routers

router = routers.SimpleRouter(trailing_slash=False)
router.register(r'', AgreementViewSet)
router.register(r'types', TypeViewSet)

urlpatterns = router.urls
