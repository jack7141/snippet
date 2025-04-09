from __future__ import unicode_literals

import logging

from rest_framework.exceptions import NotFound, ParseError, APIException, NotAcceptable

from api.bases.accounts.choices import STATUS
from api.bases.contracts.adapters import account_adapter
from api.bases.tendencies.models import Response


class AccountException(APIException):
    default_code = 'account_error'


logger = logging.getLogger('django.server')


class RiskTypeMixin(object):

    def process_discretionary(self, instance: Response):
        contracts = instance.user.contract_set.get_discretionary_contracts()
        for contract in contracts:
            try:
                if instance.risk_type is not None and not int(instance.risk_type):
                    account_adapter.update_status(contract.account_alias, status=STATUS.risk_type_suspension)
                    continue

                if instance.risk_type is not None and int(instance.risk_type):
                    response = account_adapter.request(f'/api/v1/accounts/{contract.account_alias}', method='GET')
                    account = response.json()
                    if account.get('status') is STATUS.risk_type_suspension:
                        account_adapter.update_status(contract.account_alias, status=STATUS.normal)
            except Exception as e:
                pass

            contract.change_risk_type(int(instance.risk_type))

    def process_advisory(self, instance: Response):
        contracts = instance.user.contract_set.get_advisory_contracts().filter(contract_type__fixed_risk_type=False)
        for contract in contracts:
            contract.change_risk_type(int(instance.risk_type))
