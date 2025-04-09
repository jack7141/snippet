from __future__ import absolute_import, unicode_literals
from celery import Celery
from litchi_backend import settings

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'litchi_backend.settings')

app = Celery('litchi_backend', broker=settings.BROKER_URL)

external_app = Celery('litchi_backend_external',
                      broker=settings.EXTERNAL_BROKER_URL,
                      backend=settings.EXTERNAL_BROKER_URL)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

external_app.config_from_object('django.conf:settings', namespace='CELERY')