import os
from django.conf import settings
from django.conf.urls import url, include
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), "versioned")

urlpatterns = []
version_map_dict = {}

for (
    path,
    dirs,
    files,
) in os.walk(folder):
    depth = path[len(folder) + len(os.path.sep) :].count(os.path.sep)
    if path != folder and depth == 1 and "urls.py" in files:
        version, api_name = path.split(os.path.sep)[-2:]

        if not version_map_dict.get(version, None):
            version_map_dict[version] = []

        _include = "api.versioned.{}.{}.urls".format(version, api_name)

        urlpatterns.append(
            url(r"^" + version + "/" + api_name + "/", include(_include))
        )
        version_map_dict[version].append(
            url(r"^" + api_name + "/", include(_include), name=_include)
        )

if settings.IS_DOC_ENABLED:
    for version, patterns in version_map_dict.items():
        title = "OMS API"
        base_url = "/api"
        sv = get_schema_view(
            openapi.Info(
                title=title,
                default_version=version,
                description=f"OMS {version} Api List",
                terms_of_service="https://www.google.com/policies/terms/",
                contact=openapi.Contact(email="kks@fount.co"),
                license=openapi.License(name="Fount License"),
            ),
            permission_classes=(permissions.IsAdminUser,),
        )
        urlpatterns = [
            url(
                r"^" + version + "/swagger/(?P<format>\.json|\.yaml)$",
                sv.without_ui(cache_timeout=0),
            ),
            url(r"^" + version + "/swagger/$", sv.with_ui("swagger", cache_timeout=0)),
            url(r"^" + version + "/redoc/$", sv.with_ui("redoc", cache_timeout=0)),
        ] + urlpatterns
