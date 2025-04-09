from django.conf import settings

from common.designpatterns import SingletonClass
from common.mixins import AdapterMixin
from common.utils import DotDict

__all__ = ["message_center_adapter", ]

message_center_settings = DotDict(settings.MESSAGE_CENTER_CLIENT)


class MessageCenterAdapterClass(SingletonClass, AdapterMixin):
    base = message_center_settings.BASE
    token = message_center_settings.TOKEN

    def register_mass_notification(self, items):
        resp = self.request(additional_url='/api/v1/messenger/messages/bulk',
                            data={"items": items},
                            method='POST')
        try:
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {'detail': e}


message_center_adapter = MessageCenterAdapterClass.instance()
