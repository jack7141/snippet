import os
from django.conf import settings
from django.conf.urls import url, include
from common.documentation.entities import get_swagger_view

folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'versioned')

urlpatterns = []
version_map_dict = {}

for path, dirs, files, in os.walk(folder):
    depth = path[len(folder) + len(os.path.sep):].count(os.path.sep)
    if path != folder and depth == 1 and 'urls.py' in files:
        version, api_name = path.split(os.path.sep)[-2:]

        if not version_map_dict.get(version, None):
            version_map_dict[version] = []

        _include = 'api.versioned.{}.{}.urls'.format(version, api_name)

        urlpatterns.append(url(r'^' + version + '/' + api_name + '/', include(_include)))
        version_map_dict[version].append(url(r'^' + api_name + '/', include(_include), name=_include))

if settings.DEBUG:
    for version, patterns in version_map_dict.items():
        title = 'API - {}'.format(version)
        base_url = '/api'
        docs_url = url(
            r'^' + version + '/docs/',
            get_swagger_view(title=title, patterns=patterns, url=base_url, version=version)
        )
        urlpatterns.append(docs_url)
