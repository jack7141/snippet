import logging
import json

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.cache import cache
from importlib import import_module
from django.utils.deprecation import MiddlewareMixin
from django.http.request import QueryDict

from rest_framework.status import *

logger = logging.getLogger('django.request')


class ResponseFormattingMiddleware(MiddlewareMixin):
    def process_response(self, request, response):

        try:
            if request.method == 'GET' or request.content_type == 'application/json':
                response_format = {
                    'result': {},
                    'success': is_success(response.status_code),
                    'message': response.status_text
                }
                if hasattr(response, 'data') and getattr(response, 'data') is not None:
                    response_format.update({'result': response.data})
                    data = response.data

                    for key in response_format.keys():
                        try:
                            response_format[key] = data.pop(key)
                        except:
                            pass

                response.data = response_format
                response.content = response.render().rendered_content
        except:
            pass

        return response


def is_ajax():
    return True


class PostMetaMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.content_type == 'application/json' \
                and request.method == 'POST' \
                and not request.POST \
                and request.body:
            data = QueryDict('', mutable=True)

            body = json.loads(request.body.decode('utf-8'))
            body = body[0] if isinstance(body, list) else body
            data.update(body)

            request.POST = data
            request.is_ajax = is_ajax
        return None


class LoggingMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        req_headers = {}
        req_body = {}
        res_body = {}

        for k, v in request.META.items():
            if str(k).startswith('HTTP_'):
                req_headers[str(k)] = v

        for k, v in request.POST.items():
            if k == 'password':
                req_body[k] = "*" * len(v)
            else:
                req_body[k] = v

        if hasattr(response, 'data') and isinstance(response.data, dict):
            try:
                res_body = json.dumps(response.data)
            except:
                pass

        request_log_msg = "request headers: {headers}, body: {body}".format(
            headers=json.dumps(req_headers),
            body=json.dumps(req_body)
        )

        response_log_msg = "response body: {body}".format(
            body=res_body
        )

        logger.debug(request_log_msg)
        logger.debug(response_log_msg)
        return response


class UserRestrictMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        """
        Checks if different session exists for user and deletes it.
        """
        user = getattr(request, 'user', None)
        if user and user.is_authenticated():
            cache_timeout = settings.SESSION_VENDOR_AGE if request.user.is_vendor else settings.SESSION_COOKIE_AGE
            cache_key = "user_pk_%s_restrict" % request.user.pk
            cache_value = cache.get(cache_key)

            if cache_value is not None:
                if request.session.session_key != cache_value:
                    engine = import_module(settings.SESSION_ENGINE)
                    session = engine.SessionStore(session_key=cache_value)
                    session.delete()
                    cache.set(cache_key, request.session.session_key,
                              cache_timeout)
            else:
                cache.set(cache_key, request.session.session_key, cache_timeout)

        return response


_key = getattr(settings, 'ENCRYPT_MIDDLEWARE_KEY', str(Fernet.generate_key()))
_encryptor = Fernet(_key.encode())


class EncryptMiddleware(MiddlewareMixin):
    def process_request(self, request):
        encrypt = 'encrypt' in request.GET

        if encrypt and request.content_type == 'application/json' \
                and request.method == 'POST' \
                and not request.POST \
                and request.body:
            try:
                request._body = _encryptor.decrypt(json.loads(request.body.decode('utf-8')).get('e').encode())
            except Exception as e:
                logger.error(e)
        return None
