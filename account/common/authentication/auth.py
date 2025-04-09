from importlib import import_module
import base64
import binascii

from rest_framework import HTTP_HEADER_ENCODING
from rest_framework.authentication import SessionAuthentication, TokenAuthentication, BaseAuthentication, \
    get_authorization_header
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, PermissionDenied
from rest_framework_simplejwt.authentication import api_settings, JWTAuthentication, InvalidToken

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model, authenticate
from django.core.cache import cache
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from api.bases.litchi_users.models import User as LitchiUser
from api.bases.users.models import User, ExpiringToken
from api.bases.portal.models import User as PortalUser
from common.exceptions import TokenExpired, TokenInvalid
from django.utils.translation import ugettext_lazy as _


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # To not perform the csrf check previously happening


class ExpiringSessionTokenAuthentication(TokenAuthentication):
    def __init__(self):
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    def authenticate(self, request):
        self.enforce_csrf(request)
        return super(ExpiringSessionTokenAuthentication, self).authenticate(request)

    def authenticate_credentials(self, key):
        User = get_user_model()
        session = self.SessionStore(session_key=key)
        session_load = session.load()

        if session_load:
            try:
                user = User.objects.get(id=session.get(SESSION_KEY))
            except User.DoesNotExist:
                raise AuthenticationFailed()

            if not user.is_active:
                raise NotAuthenticated()

            expiry = settings.SESSION_VENDOR_AGE if user.is_vendor else settings.SESSION_COOKIE_AGE
            session.set_expiry(expiry)
            session.save()

            # session - cache 동기화
            cache_key = "user_pk_%s_restrict" % user.pk
            cache.set(cache_key, key, expiry)

            return user, key

        return None, None

    def enforce_csrf(self, request):
        return  # To not perform the csrf check previously happening


class ExpiringTokenAuthentication(TokenAuthentication):
    model = ExpiringToken

    def authenticate_credentials(self, key):
        """Attempt token authentication using the provided key."""
        try:
            token = self.model.objects.get(key=key)
        except self.model.DoesNotExist:
            raise TokenInvalid(TokenInvalid().get_full_details())

        if not token.user.is_active:
            raise NotAuthenticated(NotAuthenticated().get_full_details())

        if token.expired():
            raise PermissionDenied()

        return (token.user, token)


class BasicAuthentication(BaseAuthentication):
    www_authenticate_realm = 'api'

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != b'basic':
            return None

        if len(auth) == 1:
            msg = _('Invalid basic header. No credentials provided.')
            raise AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = _('Invalid basic header. Credentials string should not contain spaces.')
            raise AuthenticationFailed(msg)

        try:
            auth_parts = base64.b64decode(auth[1]).decode(HTTP_HEADER_ENCODING).partition(':')
        except (TypeError, UnicodeDecodeError, binascii.Error):
            msg = _('Invalid basic header. Credentials not correctly base64 encoded.')
            raise AuthenticationFailed(msg)

        userid, password = auth_parts[0], auth_parts[2]
        return self.authenticate_credentials(userid, password, request=request)

    def authenticate_credentials(self, userid, password, request=None):
        credentials = {
            'username': userid,
            'password': password,
            'request': request
        }
        user = authenticate(**credentials)

        if user is None:
            raise AuthenticationFailed(_('Invalid username/password.'))

        if not user.is_active:
            raise AuthenticationFailed(_('User inactive or deleted.'))

        return (user, None)

    def authenticate_header(self, request):
        return 'Basic realm="%s"' % self.www_authenticate_realm


class PortalJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        """
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise InvalidToken(_('Token contained no recognizable user identification'))

        try:
            user = PortalUser.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except PortalUser.DoesNotExist:
            return super().get_user(validated_token)

        if not user.is_active:
            raise AuthenticationFailed(_('User is inactive'), code='user_inactive')

        try:
            user = User.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except User.DoesNotExist:
            user = User.objects.create(**{
                "id": user.id,
                "username": user.email,
                "email": user.email,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "password": user.password
            })
        return user
