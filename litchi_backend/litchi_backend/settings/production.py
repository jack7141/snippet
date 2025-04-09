from .base import *

# Define production settings
DEBUG = False

ALLOWED_HOSTS = ['.mkfount.com']

DATABASES = get_secret('DATABASES')

EMAIL_HOST = '175.119.156.164'
EMAIL_PORT = 25
EMAIL_MAIN = '파운트<no-reply@fount.co>'

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

CACHES = get_secret('CACHES')

INSTALLED_APPS = INSTALLED_APPS + ['elasticapm.contrib.django', ]
MIDDLEWARE = MIDDLEWARE + ['elasticapm.contrib.django.middleware.TracingMiddleware', ]

DEFAULT_FILE_STORAGE = 'common.storages.S3MediaStorage'
AWS_ACCESS_KEY_ID = get_secret('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = get_secret('AWS_SECRET_ACCESS_KEY')
AWS_S3_CUSTOM_DOMAIN = 'cdn.fount.co'
