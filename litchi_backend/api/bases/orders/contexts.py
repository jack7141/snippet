from typing import TYPE_CHECKING
from common.contexts import MessageContext, NotiTopic, NotiStatus, NotiStep
from api.bases.contracts.choices import ContractChoices

if TYPE_CHECKING:
    from api.bases.orders.models import Order


class OrderContext(MessageContext):
    ORDER_STATUS_MAP = {
        ContractChoices.ORDER_STATUS.processing: NotiStatus.IS_STARTED,
        ContractChoices.ORDER_STATUS.completed: NotiStatus.IS_COMPLETE
    }
    TOPIC_STEP_MAP = {
        ContractChoices.ORDER_MODES.new_order: (NotiTopic.NEW_ORDER, NotiStep.STEP1),
        ContractChoices.ORDER_MODES.rebalancing: (NotiTopic.REBALANCING, NotiStep.STEP1),
        ContractChoices.ORDER_MODES.sell: (NotiTopic.REBALANCING, NotiStep.STEP1),
        ContractChoices.ORDER_MODES.buy: (NotiTopic.REBALANCING, NotiStep.STEP2),
    }
    DEFAULT_ALIAS_MAP = {
        'PA': '노후대비',
        'FA': '자산관리',
        'EA': '자산관리',
        'OEA': '자산관리',
    }

    def __init__(self, instance, **kwargs):
        super().__init__(**kwargs)
        self.instance: Order = instance
        self._topic, self._step = self.get_topic_step()
        self._status = self.get_order_status()

    def get_topic_step(self):
        _topic, _step = self.TOPIC_STEP_MAP.get(self.instance.mode, ('', ''))
        return _topic, _step

    def get_order_status(self):
        return self.ORDER_STATUS_MAP.get(self.instance.status, '')

    @property
    def contract(self):
        return self.instance.order_item

    @property
    def product_code(self):
        return self.contract.contract_type.code

    @property
    def product_name(self):
        return self.contract.contract_type.name
