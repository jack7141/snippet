from __future__ import absolute_import, unicode_literals
from litchi_backend import settings

if settings.USE_CELERY is True:
    # This will make sure the app is imported when
    # Django starts if ENV not base, so that shared_task will use this app.
    from .celery import app as celery_app

    __all__ = ['celery_app']
