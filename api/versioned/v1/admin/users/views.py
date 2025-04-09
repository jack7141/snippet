from django.utils import timezone
from rest_framework import viewsets, filters
from rest_framework.response import Response
from api.bases.users.models import ExpiringToken, User, Profile

from api.versioned.v1.admin.users.serializers import (
    UserSerializer,
    UserSimpleSerializer,
    UserTokenSerializer,
)

from api.versioned.v1.users.serializers import (
    ProfileSerializer
)

from common.viewsets import AdminViewSetMixin, MappingViewSetMixin


class TokenAdminViewSet(AdminViewSetMixin,
                        viewsets.ModelViewSet):
    """
    expired: [토큰 강제만료]

    토큰을 입력 받아 만료 기간을 1일전으로 변경하여 강제 만료 처리합니다.
    """
    serializer_class = UserTokenSerializer
    queryset = ExpiringToken.objects.all()

    def expired(self, request, *args, **kwargs):
        queryset = self.get_queryset().filter(key=self.kwargs[self.lookup_field])
        queryset.update(updated=timezone.now() - timezone.timedelta(days=1))
        serializer = self.get_serializer(queryset.get())

        return Response(serializer.data)


class UserAdminViewSet(AdminViewSetMixin,
                       MappingViewSetMixin,
                       viewsets.ModelViewSet):
    """
    list: [사용자 전체조회]
    사용자 목록을 조회합니다.</br>
    조회시 search 키워드로 검색가능한 필드 : 이름, 휴대폰번호, 이메일

    retrieve : [사용자 조회]

    partial_update: [사용자 이메일 업데이트]
    사용자 이메일을 업데이트합니다.</br>
    """
    serializer_action_map = {
        'list': UserSimpleSerializer,
        'retrieve': UserSimpleSerializer,
        'partial_update': UserSerializer
    }
    queryset = User.objects.all()
    filter_backends = (filters.OrderingFilter, filters.SearchFilter,)
    search_fields = ('profile__name', 'profile__phone', 'email')


class UserProfileAdminViewSet(AdminViewSetMixin,
                              viewsets.ModelViewSet):
    """
    retrieve: [사용자 프로필 상세 조회]
    partial_update: [사용자 프로필 업데이트]
    특정 사용자의 프로필을 업데이트 합니다. 업데이트시 부분만 업데이트 가능합니다.
    """
    serializer_class = ProfileSerializer
    queryset = Profile.objects.all()
