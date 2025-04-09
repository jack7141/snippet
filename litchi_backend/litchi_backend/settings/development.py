from .base import *

# Define development settings
DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = get_secret('DATABASES')
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'common.authentication.auth.ExpiringTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'common.authentication.auth.BasicAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'common.pagenator.StandardPagination',
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_THROTTLE_RATES': {
        'sms_cert': '5/minute',
        'account_cert': '5/minute',
        'validate_email': '5/minute',
    }
}

EMAIL_USE_TLS = True
EMAIL_HOST = 'smtp.sendgrid.com'
EMAIL_PORT = 587

EMAIL_HOST_USER = get_secret('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = get_secret('EMAIL_HOST_PASSWORD')

EMAIL_MAIN = 'no-reply@fount.co'

# Setting for celery
BROKER_URL = get_secret('REDIS_HOST')
BROKER_VHOST = '0'

CELERY_RESULT_BACKEND = get_secret('REDIS_HOST')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_REDIS_DB = 0

CELERY_BEAT_SCHEDULE = {
    'task-send-mail': {
        'task': 'api.bases.users.tasks.task_send_queue_email',
        'schedule': 3.0,
    }
}

INSTALLED_APPS = INSTALLED_APPS + ['elasticapm.contrib.django', ]
MIDDLEWARE = MIDDLEWARE + ['common.middleware.LoggingMiddleware',
                           'elasticapm.contrib.django.middleware.TracingMiddleware', ]

CACHES = get_secret('CACHES')
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGIN_WHITELIST = (
    'dev-m.fount.co',
    'localhost:3000',
    '127.0.0.1:3000',
)

DEFAULT_FILE_STORAGE = 'common.storages.S3MediaStorage'
AWS_ACCESS_KEY_ID = get_secret('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = get_secret('AWS_SECRET_ACCESS_KEY')
AWS_S3_CUSTOM_DOMAIN = 'cdn.fount.co'