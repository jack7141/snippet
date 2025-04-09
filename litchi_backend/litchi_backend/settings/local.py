from .base import *

# Define local settings
DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = get_secret('DATABASES')

EMAIL_MAIN = 'no-reply@fount.co'
EMAIL_USE_TLS = True
EMAIL_HOST = 'smtp.sendgrid.com'
EMAIL_PORT = 587

EMAIL_HOST_USER = get_secret('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = get_secret('EMAIL_HOST_PASSWORD')

EMAIL_MAIN = '파운트 투자자문<no-reply@fount.co>'

CACHES = get_secret('CACHES')

CORS_ORIGIN_WHITELIST = (
    'localhost:3000',
    'localhost',
    '127.0.0.1:3000'
    '127.0.0.1',
    'dev-m.fount.co',
)
