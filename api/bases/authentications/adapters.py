import requests
import json
import logging
from urllib.parse import urljoin

from django.utils import timezone
from django.conf import settings

from rest_framework import status

from common.designpatterns import SingletonClass
from common.utils import DotDict

from api.versioned.v1.authentications.threads import HttpARSRequest

logger = logging.getLogger('django.server')

__all__ = ["ktfc_adapter", "ars_adapter", "owner_adapter"]

api_settings = DotDict(settings.KFTC_CLIENT)
ars_settings = DotDict(settings.ARS_CLIENT)
owner_settings = DotDict(settings.OWNER_CLIENT)


class KFTCAdapterClass(SingletonClass):
    __base = api_settings.BASE
    __id = api_settings.ID
    __secret = api_settings.SECRET
    __transfer_pass = api_settings.TRANSFER_PASS

    def _get_token(self):
        """
        Token format:
        {
            'client_use_code': 'string',
            'token_type': 'string',
            'access_token': 'uuid',
            'scope': 'string',
            'expires_in': miliseconds
        }
        """
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'
        }

        data = {
            'client_id': self.__id,
            'client_secret': self.__secret,
            'scope': 'oob',
            'grant_type': 'client_credentials'
        }

        response = requests.request(
            'POST',
            "https://testapi.open-platform.or.kr" + '/oauth/2.0/token',
            headers=headers, data=data
        )
        result = json.loads(response.text) if status.is_success(response.status_code) else {}
        result.update({'request_date': timezone.now()})

        self._expires_in = result.get('expires_in', None)
        self._request_date = result.get('request_date', None)
        self._access_token = result.get('access_token', None)
        self._token = result
        return result

    @property
    def access_token(self):
        if not hasattr(self, '_token'):
            self._get_token()
        if timezone.now() - self._request_date > timezone.timedelta(seconds=self._expires_in):
            self._get_token()
        return self._access_token

    def get_header(self):
        return {
            'Authorization': 'Bearer ' + self.access_token
        }

    def get_transfer_format(self, bank_code_std=None, account_number=None, account_holder_name=None, code=None):
        return {
            'wd_pass_phrase': self.__transfer_pass,
            'wd_print_content': '보냄',
            'tran_dtime': timezone.now().strftime("%Y%m%d%H%M%S"),
            'req_cnt': '1',
            'req_list': [
                {
                    "tran_no": "1",
                    "bank_code_std": bank_code_std,
                    "account_num": account_number,
                    "account_holder_name": account_holder_name,
                    "print_content": code,
                    "tran_amt": "1",
                    "cms_no": " "
                }
            ]
        }

    def request(self, additional_url, data, method="POST"):
        url = urljoin(self.__base, additional_url)

        response = requests.request(
            method,
            url,
            headers=self.get_header(),
            data=json.dumps(data)
        )

        if not response:
            logger.warning(
                'received the error response. %s %s %s %s\n%s' %
                (method, url, response.status_code, len(response.content), response.text))

        return response


class OwnerAdapterClass(SingletonClass):
    __base = owner_settings.BASE
    __auth_key = owner_settings.AUTH_KEY
    __compcode = owner_settings.SERVICE_CODE

    def get_transfer_format(self, bank_code_std=None, birth_date=None, account_number=None, seq_no='000001',
                            auth_type='99'):
        """
        :param bank_code_std: 계좌은행코드
        :param birth_date: 신원확인번호(생년월일)
        :param account_number: 계좌번호
        :param seq_no: 일련번호
        :param fcs_cd: 펌뱅킹 시스템 코드
        :param auth_type: 인증 타입
        :return:
        """
        body = {
            'auth_key': self.__auth_key,
            'reqdata': [{
                'bank_cd': bank_code_std,
                'acct_no': account_number,
                'auth_type': auth_type,
                'fcs_cd': self.__compcode,
                'seq_no': seq_no,
                'id_no': str(birth_date).replace('-', '')[2:]
            }]
        }
        return {'JSONData': json.dumps(body)}

    def get_header(self):
        return {'content-type': 'application/x-www-form-urlencoded; charset=UTF-8'}

    def request(self, data, method="POST"):
        response = requests.request(method, self.__base, headers=self.get_header(), data=data)

        if not response:
            logger.warning(
                'received the error response. %s %s %s %s\n%s' %
                (method, self.__base, response.status_code, len(response.content), response.text))

        return response


class ARSAdapterClass(SingletonClass):
    __base = ars_settings.BASE
    __auth_key = ars_settings.AUTH_KEY
    __compcode = ars_settings.SERVICE_CODE

    def get_header(self):
        return {'content-type': 'application/x-www-form-urlencoded; charset=UTF-8'}

    def get_transfer_format(self,
                            birth_date=None,
                            account_number=None,
                            name=None,
                            phone=None,
                            security=None,
                            bank_name=None,
                            service='0002',
                            service_type='03',
                            is_record='Y'):
        """
        :param birth_date: 생년월일
        :param account_number: 자동이체 계좌번호
        :param name: 이름
        :param phone: 휴대폰번호
        :param security: 인증번호
        :param bank_name: 자동이체 은행명
        :param service: 서비스 분류
        :param service_type: 서비스 기능 분류
        :param is_record: 녹취 파일 사용 유무
        :return:
        """
        body = {
            'auth_key': self.__auth_key,
            'reqdata': [{
                'birthday': str(birth_date).replace('-', ''),
                'acctno': account_number,
                'usedrecord': is_record,
                'custnm': name,
                'authno': security,
                'service': service,
                'compcode': self.__compcode,
                'phoneno': phone,
                'svc_type': service_type,
                'banknm': bank_name
            }]
        }
        return {'JSONData': json.dumps(body)}

    def request(self, data, method="POST"):
        response = requests.request(method, self.__base, headers=self.get_header(), data=data)

        if not response:
            logger.warning(
                'received the error response. %s %s %s %s\n%s' %
                (method, self.__base, response.status_code, len(response.content), response.text))

        return response

    def request_thread(self, data, method="POST", auth_id=None):
        """
        :param data: post 요청시 담길 data
        :param method: get, post, heads
        :return:
        """
        thread = HttpARSRequest(method, self.__base, headers=self.get_header(), data=data, auth_id=auth_id)
        thread.setDaemon(True)
        thread.start()


ktfc_adapter = KFTCAdapterClass.instance()
ars_adapter = ARSAdapterClass.instance()
owner_adapter = OwnerAdapterClass.instance()
