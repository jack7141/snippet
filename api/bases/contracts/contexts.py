import logging
from typing import TYPE_CHECKING

from api.bases.contracts.adapters import firmbanking_adapter
from api.bases.contracts.choices import ContractTypeChoices

from common.decorators import cached_property
from common.contexts import (
    MessageContext,
    NotiStep,
)
from common.contexts import (
    format_vendor_acct, acct_masking
)

if TYPE_CHECKING:
    from api.bases.contracts.models import Contract, Rebalancing, Transfer, get_contract_status

logger = logging.getLogger('django.server')


class ContractContextBehavior:
    OPERATION_TYPE_MAP = {
        "A": "자문계약",
        "D": "일임계약"
    }

    def is_canceled(self):
        return self.contract.status.code == get_contract_status(type='canceled', code=True) and \
               self.contract.canceled_at

    def is_rebalancing(self):
        return self.contract.status.code == get_contract_status(type='normal', code=True) and \
               self.contract.rebalancing

    @staticmethod
    def format_won_value(num: int):
        return f'{int(num):,}'

    @property
    def contract(self):
        raise NotImplementedError("need to be defined")

    @property
    def contract_type(self):
        return self.OPERATION_TYPE_MAP[self.contract.contract_type.operation_type]

    @property
    def vendor_name(self):
        return self.contract.vendor.vendor_props.company_name

    @property
    def product_code(self):
        return self.contract.contract_type.code

    @property
    def product_name(self):
        return self.contract.contract_type.name

    @property
    def account_number(self):
        acct_no = acct_masking(acct_no=self.contract.account_number)
        return format_vendor_acct(vendor_acct=acct_no,
                                  vendor_code=self.contract.vendor.vendor_props.code)

    @property
    def canceled_date(self):
        return self.contract.canceled_at.strftime('%Y-%m-%d')

    @cached_property
    def advisor_fee(self):
        if self.contract.contract_type.fee_type == ContractTypeChoices.FEE_TYPE.free:
            return "0"
        try:
            account_alias = self.contract.account_alias
            fee = firmbanking_adapter.get_advisor_fee(account_alias=account_alias)
            if fee is not None:
                return self.format_won_value(num=int(fee))
            return fee
        except Exception:
            logger.warning("Fail to get Firmbanking advisor fee")
            return None


class ContractContext(ContractContextBehavior, MessageContext):
    def __init__(self, instance, **kwargs):
        super().__init__(**kwargs)
        self.instance: Contract = instance

    @property
    def contract(self):
        return self.instance


class TransferContext(ContractContextBehavior, MessageContext):
    def __init__(self, instance, **kwargs):
        super().__init__(**kwargs)
        self.instance: Transfer = instance

    @property
    def contract(self):
        return self.instance.contract

    @property
    def opponent_vendor_name(self):
        return self.instance.vendor

    @property
    def opponent_account_number(self):
        return acct_masking(acct_no=self.instance.account_number)


class RebalancingContext(ContractContextBehavior, MessageContext):
    def __init__(self, instance, **kwargs):
        super().__init__(**kwargs)
        self.instance: Rebalancing = instance

        if not self._step:
            if self.instance.sold_at is None:
                self._step = NotiStep.STEP1
            elif self.instance.bought_at is None:
                self._step = NotiStep.STEP2

    @property
    def contract(self):
        return self.instance.contract
