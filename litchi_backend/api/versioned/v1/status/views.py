from rest_framework import viewsets
from rest_framework.serializers import Serializer
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.status import HTTP_200_OK


class StatusViewSet(viewsets.ReadOnlyModelViewSet):
    """
    status: 상태 체크

    Kibana Heartbeat 상태 체크용 API 입니다.
    """
    permission_classes = [AllowAny, ]
    serializer_class = Serializer

    def status(self, request, *args, **kwargs):
        return Response(status=HTTP_200_OK)