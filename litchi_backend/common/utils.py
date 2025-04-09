import re
import pytz
import datetime
import inspect
import uuid
import warnings
import collections

from calendar import timegm
from enum import Enum
from django.utils import timezone

from rest_framework import serializers
from rest_framework_jwt.utils import jwt_decode_handler
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.compat import get_username, get_username_field

from django.core.mail import get_connection, EmailMultiAlternatives


def get_serializer_class(_model, fields=None, exclude_fields=None):
    class SerializerClass(serializers.ModelSerializer):
        class Meta:
            model = _model

        if fields:
            setattr(Meta, 'fields', fields)

        if exclude_fields:
            setattr(Meta, 'exclude', exclude_fields)

        if not fields and not exclude_fields:
            setattr(Meta, 'fields', '__all__')

    return SerializerClass


def jwt_payload_handler(user):
    username_field = get_username_field()
    username = get_username(user)
    user_settings = api_settings.user_settings

    warnings.warn(
        'The following fields will be removed in the future: '
        '`email` and `user_id`. ',
        DeprecationWarning
    )

    exp = user_settings.get('JWT_VENDOR_EXPIRATION_DELTA') if \
        user.is_vendor else user_settings.get('JWT_EXPIRATION_DELTA')

    payload = {
        'user_id': user.pk,
        'username': username,
        'exp': datetime.datetime.utcnow() + exp
    }
    if hasattr(user, 'email'):
        payload['email'] = user.email
    if isinstance(user.pk, uuid.UUID):
        payload['user_id'] = str(user.pk)

    payload[username_field] = username

    # Include original issued at time for a brand new token,
    # to allow token refresh
    if api_settings.JWT_ALLOW_REFRESH:
        payload['orig_iat'] = timegm(
            datetime.datetime.utcnow().utctimetuple()
        )

    if api_settings.JWT_AUDIENCE is not None:
        payload['aud'] = api_settings.JWT_AUDIENCE

    if api_settings.JWT_ISSUER is not None:
        payload['iss'] = api_settings.JWT_ISSUER

    return payload


def jwt_response_payload_handler(token, user=None, request=None):
    decode = jwt_decode_handler(token)
    response_data = {
        'payload': {
            'token': token,
            'orig_iat': decode['orig_iat'],
            'exp': decode['exp']
        }
    }

    return response_data


def camel_to_snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def get_start_today(time=datetime.datetime.today()):
    return time.replace(hour=0, minute=0, second=0, microsecond=0)


class StrEnum(str, Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class ChoiceEnum(Enum):
    @classmethod
    def choices(cls):
        # get all members of the class
        members = inspect.getmembers(cls, lambda m: not (inspect.isroutine(m)))
        # filter down to just properties
        props = [m for m in members if not (m[0][:2] == '__')]
        # format into django choice tuple
        choices = tuple([(str(p[1].value), p[0]) for p in props])
        return choices

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)


def send_mass_html_mail(datatuple, fail_silently=False, auth_user=None,
                        auth_password=None, connection=None):
    """
    Given a datatuple of (subject, message, from_email, recipient_list), sends
    each message to each recipient list. Returns the number of emails sent.

    If from_email is None, the DEFAULT_FROM_EMAIL setting is used.
    If auth_user and auth_password are set, they're used to log in.
    If auth_user is None, the EMAIL_HOST_USER setting is used.
    If auth_password is None, the EMAIL_HOST_PASSWORD setting is used.

    Note: The API for this method is frozen. New code wanting to extend the
    functionality should use the EmailMessage class directly.
    """
    connection = connection or get_connection(
        username=auth_user,
        password=auth_password,
        fail_silently=fail_silently,
    )
    messages = []
    for subject, text, html, from_email, recipient in datatuple:
        message = EmailMultiAlternatives(subject, text, from_email, recipient)
        message.attach_alternative(html, 'text/html')
        messages.append(message)
    return connection.send_messages(messages)


def merge(source, destination):
    """
    run me with nosetests --with-doctest file.py

    >>> a = { 'first' : { 'all_rows' : { 'pass' : 'dog', 'number' : '1' } } }
    >>> b = { 'first' : { 'all_rows' : { 'fail' : 'cat', 'number' : '5' } } }
    >>> merge(b, a) == { 'first' : { 'all_rows' : { 'pass' : 'dog', 'fail' : 'cat', 'number' : '5' } } }
    True
    """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge(value, node)
        else:
            destination[key] = value

    return destination


class DotDict(dict):
    """
    a dictionary that supports dot notation
    as well as dictionary access notation
    usage: d = DotDict() or d = DotDict({'val1':'first'})
    set attributes: d.val2 = 'second' or d['val2'] = 'second'
    get attributes: d.val2 or d['val2']
    """
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def __init__(self, dct):
        for key, value in dct.items():
            if hasattr(value, 'keys'):
                value = DotDict(value)
            self[key] = value


def to_kst(dt: datetime, oclock=False):
    if oclock:
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

    kst_tz = pytz.timezone('Asia/Seoul')
    if timezone.is_aware(dt):
        return timezone.localtime(dt, kst_tz)
    return timezone.make_aware(dt, kst_tz)
