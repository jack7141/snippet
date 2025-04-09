from rest_framework import status
from rest_framework.exceptions import APIException
from django.utils.translation import ugettext_lazy as _


class ExpiredException(APIException):
    status_code = status.HTTP_408_REQUEST_TIMEOUT


class TokenInvalid(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Invalid token.')
    default_code = 'token_invalid'


class TokenExpired(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Token has expired.')
    default_code = 'token_expired'


class DuplicateAccess(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('Duplicate Accessed.')
    default_code = 'duplicate_access'


class ConflictException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _('Conflicted.')
    default_code = 'item conflicted.'


class PreconditionFailed(APIException):
    status_code = status.HTTP_412_PRECONDITION_FAILED
    default_detail = _('Precondition Failed.')
    default_code = 'precondition failed.'


class PreconditionRequired(APIException):
    status_code = status.HTTP_428_PRECONDITION_REQUIRED
    default_detail = _('Precondition Required.')
    default_code = 'precondition required.'


class NoMatchedAccount(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = {
                      "code": f"ACCT-NONE-{status_code}00",
                      "detail": "계좌 조회 실패",
                      "message": "Litch-Account에 존재하지 않는 계좌입니다."
                    }
    default_code = 'Not Found Account_alias.'
