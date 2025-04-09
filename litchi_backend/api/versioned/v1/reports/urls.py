from django.conf.urls import url
from common.routers import CustomSimpleRouter
from .views import (
    ManagementReportViewSet,
    ManagementReportHeaderViewSet
)


router = CustomSimpleRouter()
router.register('management/headers', ManagementReportHeaderViewSet)

urlpatterns = router.urls + [
    url(r'^management/(?P<year>[0-9]+)/(?P<quarter>[0-9])/(?P<contract_id>[0-9a-f-]+)$',
        ManagementReportViewSet.as_view({'get': 'retrieve', })),
    url(r'^management/(?P<contract_id>[0-9a-f-]+)$',
        ManagementReportViewSet.as_view({'get': 'list_report_by_contract'})),
]
