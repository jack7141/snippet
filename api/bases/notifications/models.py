import uuid
import logging

from django.db import models
from django.conf import settings
from django.core.mail import get_connection, EmailMultiAlternatives
from django.template import Template, Context
from django.utils.translation import ugettext_lazy as _

from api.bases.sms.models import ScTran, MmsMsg
from api.bases.notifications.adapters import message_center_adapter
from api.bases.notifications.choices import NotificationChoices, NotificationsSettings

from common.models import JSONField

logger = logging.getLogger('django.server')


class Topic(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, auto_created=True, unique=True, primary_key=True)
    name = models.CharField(max_length=64, null=False, blank=False, help_text='주제 명', unique=True)
    description = models.CharField(max_length=64, null=True, blank=True, help_text='주제에 대한 설명')

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('-name',)


class Notification(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, auto_created=True, unique=True, primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE,
                             help_text='수신자')
    register = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='notification_register',
                                 on_delete=models.CASCADE, help_text='등록자')
    protocol = models.CharField(max_length=1, choices=NotificationChoices.PROTOCOLS, null=True, blank=True, help_text='전송 방법')
    topic = models.ForeignKey(Topic, null=True, on_delete=models.SET_NULL, help_text='전송 주제')
    title = models.CharField(max_length=128, null=True, blank=True, help_text='알림 제목')
    message = models.TextField(blank=True, help_text='알림 내용')
    status = models.BooleanField(default=True, help_text='전송 상태')
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    context = JSONField(default={}, help_text="메시지 컨텍스트")

    def generate_sms_tr(self, title, msg, phone):
        msg = '{prefix}{msg}'.format(prefix=NotificationsSettings.sms_prefix, msg=msg)
        if len(msg.encode('euckr')) <= 90:
            return ScTran(tr_msg=msg, tr_phone=phone)
        else:
            return MmsMsg(subject=title, msg=msg, phone=phone)

    def send_mass_sms(self, queryset):
        sms_list = []
        lms_list = []
        tr_msg_list = [
            {
                "msg": '{msg}'.format(
                    msg=Template(self.message).render(Context({'user': subscribe.user,
                                                               'app_link_url': NotificationsSettings.APP_LINK_URL,
                                                               'contract_tel': NotificationsSettings.ONTRACT_TEL}))),
                "phone": subscribe.user.profile.phone
            } for subscribe in queryset
        ]

        for tr in tr_msg_list:
            tr_item = self.generate_sms_tr(self.title, tr['msg'], tr['phone'])

            if isinstance(tr_item, ScTran):
                sms_list.append(tr_item)
            elif isinstance(tr_item, MmsMsg):
                lms_list.append(tr_item)

        if sms_list:
            ScTran.objects.bulk_create(sms_list)
        if lms_list:
            MmsMsg.objects.bulk_create(lms_list)

    def send_mass_kakao_notification(self, queryset):
        noti_list = list(self.iter_notification(queryset=queryset, protocol='kakao'))
        if noti_list:
            message_center_adapter.register_mass_notification(items=noti_list)

    def iter_notification(self, queryset, protocol):
        for subscribe in queryset.iterator():
            _context = self.context.copy()
            template_id = _context.pop('template_id', '')
            if template_id:
                noti = {
                    'protocol': protocol,
                    'template': template_id,
                    'user': subscribe.user.id.hex,
                    'context': _context
                }
                yield noti
            else:
                logger.error(f"Fail to parse Notification ID: {_context}")

    def send_notification(self):
        protocol = [self.protocol] if self.protocol else [NotificationChoices.PROTOCOLS.sms,
                                                          NotificationChoices.PROTOCOLS.push]
        queryset = self.topic.subscribe_set.filter(type__in=protocol)
        if self.user:
            queryset = queryset.filter(user=self.user)

        if NotificationChoices.PROTOCOLS.sms in protocol:
            message_queryset = queryset.filter(user__profile__phone__isnull=False,
                                               type=NotificationChoices.PROTOCOLS.sms)
            self.send_mass_kakao_notification(queryset=message_queryset)

        if NotificationChoices.PROTOCOLS.email in protocol:
            connection = get_connection()
            messages = []

            for subscribe in queryset.filter(type=NotificationChoices.PROTOCOLS.email):
                content = Template(self.message).render(Context({'user': subscribe.user,
                                                                 'app_link_url': NotificationsSettings.APP_LINK_URL,
                                                                 'contract_tel': NotificationsSettings.CONTRACT_TEL}))
                subject = Template(self.title).render(Context({'user': subscribe.user}))

                msg = EmailMultiAlternatives(subject, content, settings.EMAIL_MAIN, [subscribe.user.email])
                msg.attach_alternative(content, "text/html")
                messages.append(msg)

            connection.send_messages(messages)
            connection.close()
        if NotificationChoices.PROTOCOLS.push in protocol:
            registration_ids = []
            for query in queryset.filter(type=NotificationChoices.PROTOCOLS.push):
                registration_ids += list(query.user.device_set.filter(active=True)
                                         .values_list('registration_id', flat=True).distinct())
            if registration_ids:
                noti_list = [
                    {
                        "protocol": "push",
                        "contract": registration_id,
                        "message": self.message,
                        "title": self.title
                    } for registration_id in registration_ids
                ]
                message_center_adapter.register_mass_notification(items=noti_list)

    class Meta:
        ordering = ['-created_at']


class Subscribe(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, auto_created=True, unique=True, primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type = models.CharField(max_length=1, choices=NotificationChoices.PROTOCOLS, null=False, blank=False,
                            help_text='protocol 종류')
    topics = models.ManyToManyField(Topic, help_text='주제 목록', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성 일자')

    class Meta:
        unique_together = ('user', 'type')
        ordering = ('-created_at',)


class Device(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, auto_created=True, unique=True, primary_key=True)
    name = models.CharField(max_length=255, verbose_name=_("Name"), blank=True, null=True)
    active = models.BooleanField(
        verbose_name=_("Is active"), default=True,
        help_text=_("Inactive devices will not be sent notifications")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(
        verbose_name=_("Creation date"), auto_now_add=True, null=True
    )
    application_id = models.CharField(
        max_length=64, verbose_name=_("Application ID"),
        help_text=_(
            "Opaque application identity, should be filled in for multiple"
            " key/certificate access"
        ),
        blank=True, null=True
    )
    registration_id = models.TextField(verbose_name=_("Registration ID"))
    failed_count = models.PositiveSmallIntegerField(default=0, blank=False, null=False)

    def __str__(self):
        return (
                self.name or str(self.id or "") or
                "%s for %s" % (self.__class__.__name__, self.user or "unknown user")
        )

    class Meta:
        ordering = ('user',)
