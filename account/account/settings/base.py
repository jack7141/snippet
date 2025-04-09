"""
Django settings for account project.

Generated by 'django-admin startproject' using Django 3.1.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

import json
import os
from datetime import timedelta

from django.conf import global_settings
from django.core.exceptions import ImproperlyConfigured

from common.utils import DotDict

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

secret_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'secrets.json')

with open(secret_file, encoding='utf-8') as f:
    secrets = DotDict(json.loads(f.read()))


def get_secret(setting, secrets=secrets):
    """비밀 변수를 가져오거나 명시적 예외를 반환한다."""
    try:
        # if secrets.get(setting, None) else
        return secrets.get(setting) if secrets.get(setting, None) \
            else (getattr(global_settings, setting) if hasattr(global_settings, setting) else eval(setting))

        # return secrets[setting] if secrets[setting] else eval(setting)
    except KeyError:
        error_msg = "Set the {} environment variable".format(setting)
        raise ImproperlyConfigured(error_msg)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_secret('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
SITE_ID = 1

ALLOWED_HOSTS = ['*']
TR_BACKEND = get_secret("TR_BACKEND")
HANAW_BACKEND = get_secret("HANAW_BACKEND")

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'drf_yasg',
    'corsheaders',
    'rest_framework',
    'reversion',
    'django_admin_inline_paginator',
    'django_celery_beat',
    'django_celery_results',
    'api.bases.users',
    'api.bases.litchi_users',
    'api.bases.portal',
    'api.bases.accounts',
    'api.bases.forex',
    'api.bases.orders',
    'api.bases.infomax',
]

AUTH_USER_MODEL = 'users.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'reversion.middleware.RevisionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'account.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')]
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'account.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    },
    "litchi": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "litchi_db.sqlite3"),
    },
    "portal": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "portal_db.sqlite3"),
    },
    "portfolio": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "portal_db.sqlite3")
    },
    "infomax": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "portal_db.sqlite3")
    }
}

# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Seoul'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/static/'

# Documentation
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'basic': {
            'type': 'basic'
        },
        'Token': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        },
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'LOGIN_URL': '/admin/login/',
    'LOGOUT_URL': '/admin/logout/',
    'USE_SESSION_AUTH': True,
    'DOC_EXPANSION': 'None',
    'DEEP_LINKING': True,
    'DEFAULT_MODEL_DEPTH': 1,
    'DISPLAY_OPERATION_ID': False,
    'REFETCH_SCHEMA_WITH_AUTH': True,
    'REFETCH_SCHEMA_ON_LOGOUT': True
}

REDOC_SETTINGS = {
    'PATH_IN_MIDDLE': True,
    'REQUIRED_PROPS_FIRST': True
}

# Rest Framework
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'djangorestframework_camel_case.render.CamelCaseJSONRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'djangorestframework_camel_case.parser.CamelCaseFormParser',
        'djangorestframework_camel_case.parser.CamelCaseMultiPartParser',
        'djangorestframework_camel_case.parser.CamelCaseJSONParser',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'common.authentication.auth.ExpiringTokenAuthentication',
        'common.authentication.auth.PortalJWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'common.pagenator.StandardPagination',
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'JSON_UNDERSCOREIZE': {
        'no_underscore_before_number': True,
    },
}

# Database Route
DATABASE_ROUTERS = ("common.db_routers.AppLabelBaseMappingRouter",)

# Authenticate
EXPIRING_TOKEN_LIFESPAN = 60 * 30

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=90),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=120),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': 'FOUNT_INTERNAL_SYSTEM_PROJECTS',
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'email',
    'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(days=90),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=120),
}

# CELERY CONFIG
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/2')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Seoul'
