from .base import *

# Define development settings
DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = get_secret('DATABASES')
INSTALLED_APPS = INSTALLED_APPS + ['elasticapm.contrib.django', ]
MIDDLEWARE = MIDDLEWARE + ['elasticapm.contrib.django.middleware.TracingMiddleware', ]
ELASTIC_APM = {
    "SERVICE_NAME": "litchi_finance_account",
    "SECRET_TOKEN": "litchi_finance_account",
    "DEBUG": True,
    "CAPTURE_BODY": "transactions"
}

STATIC_ROOT = os.path.join(BASE_DIR, '../static')
