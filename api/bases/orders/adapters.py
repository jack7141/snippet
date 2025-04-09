import requests
import json
import logging

from urllib.parse import urljoin

from django.conf import settings

from common.exceptions import PreconditionFailed
from common.designpatterns import SingletonClass
from common.utils import DotDict

logger = logging.getLogger('django.server')

__all__ = ["ea_oms_settings", ]

ea_oms_settings = DotDict(settings.EA_OMS_CLIENT)


class EAOMSAdapterClass(SingletonClass):
    __base = ea_oms_settings.BASE
    __token = ea_oms_settings.TOKEN

    def get_header(self):
        return {
            'Content-Type': 'application/json',
            'Authorization': 'Token ' + self.__token
        }

    def get_access_token(self, ci, birth_date, gender_code, name, phone):
        url = f'/api/v2/orders/access-token'
        birth_date = str(birth_date).replace('-', '')[2:]
        user_info = '|'.join([birth_date + str(gender_code), name, phone])
        response = self.request(url, data={'ci_no': ci, 'user_info': user_info})
        return response.json().get('access_token')

    def get_order_basket(self, access_token, account_alias, universe_index='2083'):
        resp = self.request(
            additional_url=f'/api/v2/orders/basket',
            data={'access_token': access_token, 'account_alias': account_alias, 'universe_index': universe_index},
            method='POST')
        if not resp:
            raise PreconditionFailed(resp.json())
        return resp.json()

    def create_order(self, access_token, account_alias, password):
        resp = self.request(additional_url=f'/api/v2/orders/',
                            data={'access_token': access_token, 'account_alias': account_alias,
                                  'password': password},
                            method='POST')
        if not resp:
            raise PreconditionFailed(resp.json())
        return resp.json()

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


ea_oms_adapter = EAOMSAdapterClass.instance()
