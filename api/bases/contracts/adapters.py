import requests
import json
import datetime
import logging

from urllib.parse import urljoin

from django.conf import settings

from common.designpatterns import SingletonClass
from common.mixins import AdapterMixin
from common.utils import DotDict

logger = logging.getLogger('django.server')

__all__ = ["firmbanking_adapter", "account_adapter", "fep_adapter"]

firmbanking_settings = DotDict(settings.FIRMBANKING_CLIENT)
account_settings = DotDict(settings.ACCOUNT_CLIENT)
fep_settings = DotDict(settings.FEP_CLIENT)


class FirmbankingAdapterClass(SingletonClass):
    __base = firmbanking_settings.BASE
    __token = firmbanking_settings.TOKEN

    def get_header(self):
        return {
            'Authorization': 'Token ' + self.__token,
            'Content-Type': 'application/json'
        }

    def get_settlement_list(self, account_alias, type='yearly_performance_fee'):
        resp = self.request(
            additional_url=f'/api/v1/settlement/?type={type}&account_alias={account_alias}&page_size=1000',
            method='GET')
        resp.raise_for_status()
        return resp.json().get('data', [])

    def get_advisor_fee(self, account_alias):
        resp = self.request(additional_url=f'/api/v1/settlement/{account_alias}/completed/', method='GET')
        if resp.status_code == requests.codes['not_found']:
            return 0
        resp.raise_for_status()
        return resp.json().get('fees', None)

    def get_withdraw_format(self, ci=None, account_alias=None, account_number=None, birth_date=None,
                            contract_number=None, vendor=None):
        if isinstance(birth_date, datetime.date):
            birth_date = str(birth_date)

        return {
            'ci': ci,
            'vendor': vendor,
            'account_alias': account_alias,
            'account_number': account_number,
            'birth_date': birth_date,
            'contract_number': contract_number,
        }

    def get_withdraw_monthly_format(self, ci=None, account_alias=None, account_number=None, birth_date=None,
                                    contract_number=None, version=None, vendor=None, contract_type=None):
        if isinstance(birth_date, datetime.date):
            birth_date = str(birth_date)

        return {
            'ci': ci,
            'vendor': vendor,
            'account_alias': account_alias,
            'account_number': account_number,
            'birth_date': birth_date,
            'contract_type': contract_type,
            'version': version,
            'contract_number': contract_number,
        }

    def get_register_format(self, account_number=None, birth_date=None, contract_number=None,
                            serial_number=None, bank_code=None, phone=None, auth_file=None):
        if isinstance(birth_date, datetime.date):
            birth_date = str(birth_date)

        return {
            'account_number': account_number,
            'birth_date': birth_date,
            'contract_number': contract_number,
            'serial_number': serial_number,
            'bank_code': bank_code,
            'phone': phone,
            'auth_file': auth_file
        }

    def request(self, additional_url, data=None, method="POST"):
        url = urljoin(self.__base, additional_url)
        data = json.dumps(data) if data is not None else dict()
        response = requests.request(
            method,
            url,
            headers=self.get_header(),
            data=data
        )

        if not response:
            logger.warning(
                'received the error response. %s %s %s %s - %s' %
                (method, url, response.status_code, len(response.content), response.text))

        return response


class AccountServerAdapterClass(SingletonClass, AdapterMixin):
    base = account_settings.BASE
    token = account_settings.TOKEN

    def update_status(self, account_alias, status):
        response = self.request('api/v1/accounts/{}'.format(account_alias),
                                data={'status': status},
                                method='PUT')
        return response

    def update_risk_type(self, account_alias, risk_type):
        response = self.request('api/v1/accounts/{}'.format(account_alias),
                                data={'risk_type': risk_type},
                                method='PUT')
        return response


class FEPServerAdapterClass(SingletonClass, AdapterMixin):
    base = fep_settings.BASE
    token = fep_settings.TOKEN

    def get_access_token(self, vendor_code, ci):
        url = f'/api/v1/{vendor_code}/oauth'
        return self.request(url, data={'ci_valu': ci})

    def register_third_party_agreement(self, vendor_code, ci):
        url = f'/api/v1/{vendor_code}/customer/third-party'
        return self.request(url, data={'ci_valu': ci})

    def get_vendor_data(self, vendor_code, url, account_number, account_alias, ci, method, **data):
        data = {'acct_no': account_number, 'ci_valu': ci, **data}

        if vendor_code == 'hanaw':
            data = {'acct_alias': account_alias, 'ci_valu': ci, **data}

        return self.request(url, data=data, method=method)


firmbanking_adapter = FirmbankingAdapterClass.instance()
account_adapter = AccountServerAdapterClass.instance()
fep_adapter = FEPServerAdapterClass.instance()
