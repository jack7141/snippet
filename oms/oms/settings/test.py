"""
With these settings, tests run faster.
"""

from .base import *  # noqa
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="b4ySiQpFSXOl2niZCOGJGmX1ru1ehL1dWM4S2eMg2YFLWV9VkA24KlHNqmmxYWbN",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# Your stuff...
# ------------------------------------------------------------------------------
del DATABASES["portfolio"]
