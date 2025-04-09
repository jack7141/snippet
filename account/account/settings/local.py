from .base import *

# Define local settings
DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = get_secret('DATABASES')