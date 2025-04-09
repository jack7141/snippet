from django.conf import settings
from django.utils import timezone

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from api.bases.tendencies.models import Type, Response, Reason
from api.versioned.v1.tendencies.serializers import (
    TypeSerializer, ResponseSerializer, ResponseCreateSerializer, ReasonSerializer
)
from common.exceptions import DuplicateAccess
from common.viewsets import MappingViewSetMixin


class TypeViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
      list: [투자성향 목록 조회]
      유저의 투자성향 분석 목록을 불러 옵니다.</br>

      retrieve: [투자성향 조회]
      code는 suffix로 버전 관리되며, 현재 버전은 fount로 표기 됩니다.
      ex) v1, v2,
    """
    queryset = Type.objects.filter(is_published=True).order_by('-created_at')
    serializer_class = TypeSerializer
    filter_fields = ('code',)
    lookup_field = 'code'

    permission_classes_map = {
        'retrieve': [AllowAny],
    }


class ReasonViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    list:[투자성향 사유 목록 조회]
    현재 저장된 투자성향 사유 목록을 확인합니다.</br>
    is_publish가 True인 목록만 조회됩니다.
    """
    queryset = Reason.objects.all()
    serializer_class = ReasonSerializer
    ordering_fields = ('-created_at',)

    def get_queryset(self):
        return self.queryset.filter(is_publish=True)


class ResponseViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    list:[투자성향 목록 조회]
    현재 저장된 유저의 투자성향 목록을 확인합니다.</br>

    | **생체 기반** |  | **소유 기반** |  | **지식 기반** |  |
    |:-:|:-:|:-:|:-:|:-:|:-:|
    | **status** | **defs** | **status** | **defs** | **status** | **defs** |
    | 10 | 바이오인증 | 20 | 소유주인증 | 30 | 지식기반인증 |
    | 11 | 지문 | 21 | SMS | 31 | 패스워드 |
    | 12 | 얼굴 | 22 | OTP | 32 | 패턴 |
    | 13 | 홍채 | 23 | 보안카드 | 33 | PIN |

    create:[투자성향 응답 저장]
    요청한 유저의 투자성향 응답 값을 저장합니다.</br>

    질문 갯수와 응답 갯수가 같은 경우, 질문 응답 값이 질문지와 다른 경우</br>
    HTTP_400_BAD_REQUEST를 리턴합니다.

    **기본 Code : 현재 투자성향 Type이 publish 되어있고, default로 체크된 조건**
    """
    queryset = Response.objects.all()
    serializer_class = ResponseSerializer
    ordering_fields = ('-created_at',)
    serializer_action_map = {
        'create': ResponseCreateSerializer
    }

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-created_at')

    def get_object(self):
        return self.get_queryset().get()

    def perform_create(self, serializer):
        queryset = Response.objects.filter(user=self.request.user, created_at__date=timezone.localdate())
        if queryset.count() >= settings.RESTRICT_TENDENCY_PER_DAY:
            raise DuplicateAccess(f"Restrict tendency, count: {settings.RESTRICT_TENDENCY_PER_DAY}")

        serializer.save()
