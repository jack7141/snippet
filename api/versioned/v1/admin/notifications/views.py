from rest_framework import viewsets
from common.viewsets import MappingViewSetMixin, AdminViewSetMixin

from api.bases.notifications.models import (
    Notification
)

from api.versioned.v1.notifications.serializers import (
    NotificationSerializer,
    NotificationCreateSerializer
)


class NotificationViewSet(MappingViewSetMixin,
                          AdminViewSetMixin,
                          viewsets.ModelViewSet):
    """
    list:[발송한 알림 목록 조회]
    알림 등록한 목록을 조회합니다.

    create:[알림 등록]
    알림을 등록합니다. <br/>
    알림을 지원하는 protocol은 1) SMS, 2) Email, 3) Mobile Push 로 총 3가지 입니다.<br/>
    topic은 /notifications/topic에 존재하는 목록중 1가지가 필수입니다.<strong>(UUID 포멧)</strong> <br/>
    title은 protocol이 Email인 경우 메일 제목으로 사용되고, Mobile Push의 경우 Push 제목으로 사용됩니다. <br/>

    ※ SMS는 유저의 phone 기준으로 발송됩니다. <br/>
    ※ Email은 유저의 ID 기준으로 발송됩니다. <br/>
    ※ Mobile Push는 /notificaitons/devices에서 수신 등록한 기기 기준으로 발송됩니다. <br/>
    """
    queryset = Notification.objects.all().prefetch_related('topic').select_related('user', 'register')
    serializer_class = NotificationSerializer

    serializer_action_map = {
        'create': NotificationCreateSerializer
    }
