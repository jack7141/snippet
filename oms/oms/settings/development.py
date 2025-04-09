from .base import *  # noqa
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="b4ySiQpFSXOl2niZCOGJGmX1ru1ehL1dWM4S2eMg2YFLWV9VkA24KlHNqmmxYWbN",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]

# http://whitenoise.evans.io/en/stable/django.html#using-whitenoise-in-development
INSTALLED_APPS = ["whitenoise.runserver_nostatic"] + INSTALLED_APPS
INSTALLED_APPS = INSTALLED_APPS + [
    "elasticapm.contrib.django",
]

MIDDLEWARE = MIDDLEWARE + [
    "elasticapm.contrib.django.middleware.TracingMiddleware",
]
