from django.conf.urls import url

from api.versioned.v1.agreements.views import TypeViewSet, AgreementGroupViewSet, AgreementViewSet

from rest_framework import routers

router = routers.SimpleRouter(trailing_slash=False)

router.register(r'types', TypeViewSet)
router.register(r'agreement_groups', AgreementGroupViewSet)

urlpatterns = router.urls

urlpatterns += [
    url(r'^$', AgreementViewSet.as_view({'get': 'list', 'post': 'create'})),
    url(r'^(?P<pk>[0-9a-f-]+)$', AgreementViewSet.as_view({'delete': 'destroy'})),
]
