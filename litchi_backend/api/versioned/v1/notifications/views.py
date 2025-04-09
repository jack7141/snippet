from rest_framework import viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.exceptions import ValidationError

from common.permissions import IsOwnerOrAdminUser
from common.viewsets import MappingViewSetMixin, UserQuerySetMixin

from api.bases.notifications.models import (
    Notification,
    Subscribe,
    Topic,
    Device
)
from api.bases.notifications.choices import NotificationChoices

from .filters import SubscribeFilter

from .serializers import (
    NotificationSerializer,
    SubscribeSerializer,
    SubscribeCreateSerializer,
    SubscribeUpdateSerializer,
    NoAuthSubscribeSerializer,
    TopicSerializer,
    DeviceSerializer,
    DeviceCreateSerializer
)


class NotificationViewSet(MappingViewSetMixin,
                          UserQuerySetMixin,
                          viewsets.ModelViewSet):
    """
    list:[발송한 알림 목록 조회]
    알림 등록한 목록을 조회합니다.
    ※ SMS는 유저의 phone 기준으로 발송됩니다. <br/>
    ※ Email은 유저의 ID 기준으로 발송됩니다. <br/>
    ※ Mobile Push는 /notificaitons/devices에서 수신 등록한 기기 기준으로 발송됩니다. <br/>
    """
    queryset = Notification.objects.all().prefetch_related('topic').select_related('user', 'register')
    serializer_class = NotificationSerializer
    filter_fields = ('protocol', 'topic__name',)

    def get_queryset(self):
        user = self.request.user
        topics = list(set(Topic.objects.filter(subscribe__user=self.request.user).values_list('name', flat=True)))

        queryset = self.queryset.filter(user=self.request.user) | \
                   self.queryset.filter(user=None, topic__name__in=topics, created_at__gte=user.date_joined)

        return queryset


class SubscribeViewSet(MappingViewSetMixin,
                       UserQuerySetMixin,
                       viewsets.ModelViewSet):
    """
    list:[구독 목록 조회]
    현재 구독중인 목록을 조회합니다. 관리자의 경우 전체 유저에 대한 구독 목록이 나타납니다.

    create:[구독-전송방식 등록]
    구독되지 않은 전송방식(Protocol)을 추가합니다.</br>
    구독 목록 조회 API에서 이미 전송방식이 등록되어 있으면 추가 등록할 수 없습니다.</br>
    구독 목록에 있는 프로토콜의 경우 구독 수정 API를 이용하시기 바랍니다.</br>
    회원 가입시 기본적으로 4가지 프로토콜이 전부 등록되어 있으나, 신규 프로토콜이 추가된 경우 지원하기 위한 API입니다. </br>

    ※ protocol 종류 - 1: SMS, 2: Email, 3: Mobile Push, 4: App

    retrieve:[구독 상세조회]
    특정 주제의 구독상태를 조회합니다.

    partial_update:[구독 수정]
    Protocol에 대한 구독 목록을 수정 합니다.</br>
    topics에는 구독 가능 주제들에 대한 UUID가 사용됩니다. </br>

    ※ protocol 종류 - 1: SMS, 2: Email, 3: Mobile Push, 4: App
    """
    queryset = Subscribe.objects.all().prefetch_related('topics').select_related('user')
    serializer_class = SubscribeSerializer

    serializer_action_map = {
        'create': SubscribeCreateSerializer,
        'partial_update': SubscribeUpdateSerializer
    }

    owner_field = 'user'
    permission_classes_map = {
        'partial_update': [IsOwnerOrAdminUser]
    }


class NonAuthSubscribeViewSet(SubscribeViewSet):
    """
    update:[구독 추가 - 비인증]
    현재 구독중인 protocol에 대해 주제를 추가 등록합니다.<br/>
    만약 요청한 protocol이 없다면 status_code:404로 응답합니다. <br/>

    destroy:[구독 해제 - 비인증]
    현재 구독중인 protocol에 대해 주제를 해제합니다.<br/>
    만약 요청한 protocol이 없다면 status_code:404로 응답합니다. <br/>
    """

    filter_class = SubscribeFilter
    lookup_field = 'type'
    lookup_url_kwarg = 'type_name'

    permission_classes_map = {
        'update': [AllowAny],
        'destroy': [AllowAny]
    }

    serializer_class = NoAuthSubscribeSerializer

    def get_queryset(self):
        return self.queryset

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
                'Expected view %s to be called with a URL keyword argument '
                'named "%s". Fix your URL conf, or set the `.lookup_field` '
                'attribute on the view correctly.' %
                (self.__class__.__name__, lookup_url_kwarg)
        )
        try:
            filter_kwargs = {self.lookup_field: NotificationChoices.PROTOCOLS.__getattr__(str(self.kwargs[lookup_url_kwarg]).lower())}
        except:
            filter_kwargs = {self.lookup_field: None}
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_update(self, serializer):
        try:
            serializer.instance.topics.add(Topic.objects.get(name=self.kwargs['topic_name']))
        except Topic.DoesNotExist as e:
            raise ValidationError({"topic_name": e})

    def perform_destroy(self, instance):
        try:
            instance.topics.remove(Topic.objects.get(name=self.kwargs['topic_name']))
        except Topic.DoesNotExist as e:
            raise ValidationError({"topic_name": e})


class TopicViewSet(MappingViewSetMixin, viewsets.ModelViewSet):
    """
    list:[주제 목록 조회]
    구독 가능한 주제 목록을 조회합니다.

    create:[주제 등록]
    구독 가능한 주제를 등록합니다. 관리자만 사용 가능합니다.

    destroy:[주제 삭제]
    주제를 삭제합니다. 주제를 삭제하게되면 해당 주제를 구독중인 유저들의 구독 목록에서 자동으로 주제가 없어집니다.
    """
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    permission_classes_map = {
        'create': [IsAdminUser],
        'destroy': [IsAdminUser]
    }


class DeviceViewSet(MappingViewSetMixin,
                    UserQuerySetMixin,
                    viewsets.ModelViewSet):
    """
    list: [기기 목록 조회]
    등록된 기기 목록을 조회합니다. <br/>
    사용자의 경우 자신이 등록한 목록만 조회 가능하고, 관리자는 전체 목록을 조회 할 수 있습니다.

    create: [기기 등록]
    Push 알람을 받을 기기의 토큰을 등록합니다.

    destroy: [기기 삭제]
    Push 알람을 해지할 기기를 삭제합니다.
    """
    queryset = Device.objects.all().select_related('user')
    serializer_class = DeviceSerializer

    serializer_action_map = {
        'create': DeviceCreateSerializer,
    }

    permission_classes_map = {
        'destroy': [IsOwnerOrAdminUser],
    }

    owner_field = 'user'

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(user=user,
                        name="{0}'s Device #{1}".format(
                            user.profile.name or user.email,
                            user.device_set.all().count() + 1
                        ))
