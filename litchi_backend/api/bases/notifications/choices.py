from django.conf import settings

from model_utils import Choices
from common.utils import ChoiceEnum


class NotificationsSettings:
    sms_prefix = settings.NOTIFICATIONS_SETTINGS.get('SMS_PREFIX', '[파운트]')

    APP_LINK_URL = settings.NOTIFICATIONS_SETTINGS.get('APP_LINK_URL')
    CONTRACT_TEL = settings.NOTIFICATIONS_SETTINGS.get('CONTRACT_TEL')


class ProtocolTypes(ChoiceEnum):
    Sms = 1
    Email = 2
    Push = 3


class NotificationChoices:
    PROTOCOLS = Choices(('1', 'sms', 'SMS'),
                        ('2', 'email', 'EMAIL'),
                        ('3', 'push', 'PUSH'),
                        ('4', 'app', 'APP'))