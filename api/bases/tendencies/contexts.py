import logging
from typing import TYPE_CHECKING

from common.contexts import (
    MessageContext,
)

if TYPE_CHECKING:
    from api.bases.tendencies.models import Response

logger = logging.getLogger('django.server')

INVESTOR_TYPE = ['안정적인 투자자', '합리적인 투자자', '균형잡힌 투자자', '도전적인 투자자', '모험적인 투자자']


class ResponseContextBehavior:

    @property
    def response(self):
        raise NotImplementedError("need to be defined")

    @property
    def analysis_result(self):
        return INVESTOR_TYPE[int(self.response.risk_type)]

    @property
    def analysis_date(self):
        return self.response.created_at.strftime('%Y-%m-%d')

    @property
    def last_month(self):
        return self.response.created_at.strftime('%m')

    @property
    def last_day(self):
        return self.response.created_at.strftime('%d')


class ResponseContext(ResponseContextBehavior, MessageContext):
    def __init__(self, instance, **kwargs):
        super().__init__(**kwargs)
        self.instance: Response = instance

    @property
    def response(self):
        return self.instance
