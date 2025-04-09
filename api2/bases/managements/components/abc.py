import json
from abc import ABCMeta

from django.conf import settings

from api.bases.accounts.models import Account
from api.bases.orders.models import OrderSetting
from common.utils import DotDict
from common.exceptions import MinBaseViolation


class ABCOrderManagement(metaclass=ABCMeta):
    def __init__(
        self,
        api_base,
        vendor_code,
        account_alias,
        exchange_rate,
        min_deposit_ratio,
        deposit_buffer_ratio,
        *args,
        **kwargs,
    ):
        self.__model_portfolio = None
        self.api_base = api_base
        self.vendor_code = vendor_code

        if isinstance(account_alias, Account):
            self.account = account_alias
        else:
            self.account = Account.objects.get(account_alias=account_alias)

        assert (
            exchange_rate > 0
        ), f"exchange_rate({exchange_rate}) must be larger than 0"
        self.exchange_rate = exchange_rate
        self.order_setting = self.account.order_setting
        if not self.order_setting:
            self.order_setting, is_created = OrderSetting.objects.get_or_create(
                name="default"
            )

        _strategies = self.order_setting.strategies
        if isinstance(_strategies, str):
            _strategies = json.loads(_strategies)
        self.strategies = DotDict(_strategies)
        self.min_deposit_ratio = min_deposit_ratio
        self.deposit_buffer_ratio = deposit_buffer_ratio
        self._proxy = ABCOrderAccountProxy(management=self)

    @property
    def account_number(self):
        return self.account.account_number

    @property
    def emphasis(self):
        return self.order_setting.emphasis

    @property
    def base(self):
        return self._proxy.base

    @property
    def max_ord_base(self):
        return self.base * (1 - (self.min_deposit_ratio + self.deposit_buffer_ratio))

    @property
    def shares(self):
        return self._proxy.shares

    @property
    def current_portfolio(self):
        return self._proxy.current_portfolio

    @property
    def shares_prices(self):
        return self._proxy.shares_prices

    def check_min_base(self):
        # 투자 원금 (입출금액 누계) 기준
        if not settings.ORDER_MANAGEMENT_CHECK_MIN_BASE:
            return True

        input_amount = self._proxy.get_input_amount()
        if input_amount < self.order_setting.min_base:
            raise MinBaseViolation(
                f"input_amount({input_amount}) must be larger than min_base({self.order_setting.min_base})"
            )
        return True


class ABCOrderAccountProxy(metaclass=ABCMeta):
    def __init__(self, management: "ABCOrderManagement"):
        self.manager = management
        self.shares = None
        self._base = 0

    @property
    def base(self):
        raise NotImplementedError("Need to be implemented")

    @property
    def current_portfolio(self):
        raise NotImplementedError("Need to be implemented")

    @property
    def shares_prices(self):
        raise NotImplementedError("Need to be implemented")

    def get_input_amount(self):
        raise NotImplementedError("Need to be implemented")
