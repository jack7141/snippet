from django.conf.urls import url, include

from api.versioned.v1.admin.contracts import urls as contract_urls
from api.versioned.v1.admin.firmbanking import urls as firmbanking_urls
from api.versioned.v1.admin.orders import urls as order_urls
from api.versioned.v1.admin.notifications import urls as notification_urls
from api.versioned.v1.admin.users import urls as user_urls
from api.versioned.v1.admin.agreements import urls as agreements_urls
from api.versioned.v1.admin.tendencies import urls as tendencies_urls

urlpatterns = [
    url(r'^contracts/', include(contract_urls)),
    url(r'^firmbanking/', include(firmbanking_urls)),
    url(r'^orders/', include(order_urls)),
    url(r'^notifications/', include(notification_urls)),
    url(r'^users/', include(user_urls)),
    url(r'^agreements/', include(agreements_urls)),
    url(r'^tendencies/', include(tendencies_urls)),
]
