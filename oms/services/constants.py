from rest_framework import status


class HTTPRequestVerb:
    GET = "GET"
    POST = "POST"


RETRYABLE_HTTP_STATUSES = [
    status.HTTP_408_REQUEST_TIMEOUT,
    status.HTTP_500_INTERNAL_SERVER_ERROR,
    status.HTTP_502_BAD_GATEWAY,
    status.HTTP_503_SERVICE_UNAVAILABLE,
    status.HTTP_504_GATEWAY_TIMEOUT,
]
