import logging
import threading
import requests
import json

from django.utils import timezone

from api.bases.authentications.models import Auth
from api.bases.contracts.models import Contract, get_contract_status
from api.bases.contracts.adapters import firmbanking_adapter

logger = logging.getLogger('django.server')


class HttpARSRequest(threading.Thread):
    """
    Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition.
    """

    def __init__(self, method, url, headers, data, auth_id):
        threading.Thread.__init__(self)
        self.method = method
        self.url = url
        self.headers = headers
        self.data = data
        self.auth_id = auth_id
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def run(self):
        try:
            response = requests.request(self.method, self.url, headers=self.headers, data=self.data)
            res_data = json.loads(response.text)

            if res_data['reply'] == '0000':
                Auth.objects.filter(id=self.auth_id).update(
                    is_verified=True,
                    etc_3=res_data['trace_no'],
                    etc_entrypted_text_1=res_data['record']
                )
                auth = Auth.objects.get(id=self.auth_id)

                Contract.objects.filter(id=auth.etc_2).update(firm_agreement_at=timezone.now())
                contract = Contract.objects.get(id=auth.etc_2)

                bank_code = {
                    "shinhan": "278",
                    "kb": "218"
                }.get(contract.vendor.vendor_props.code)
                account_number = contract.account_number

                if contract.vendor.vendor_props.code == 'hanaw':
                    owner_auth = Auth.objects.filter(
                        user=auth.user,
                        etc_2=auth.etc_2,
                        cert_type=4,
                        is_verified=True,
                        is_expired=False).order_by('created_date').last()
                    if owner_auth:
                        Auth.objects.filter(id=self.auth_id).update(
                            etc_encrypted_2=owner_auth.etc_1,
                            etc_encrypted_3=owner_auth.etc_encrypted_1
                        )
                        account_number = owner_auth.etc_encrypted_1
                        bank_code = owner_auth.etc_1

                # 출금이체 계좌등록 - 계좌 등록 요청만 하도록 함
                data = firmbanking_adapter.get_register_format(account_number=account_number,
                                                               birth_date=contract.user.profile.birth_date,
                                                               contract_number=contract.contract_number,
                                                               serial_number=auth.etc_3,
                                                               bank_code=bank_code,
                                                               phone=auth.etc_1,
                                                               auth_file=auth.etc_entrypted_text_1)
                response = firmbanking_adapter.request('api/v1/firmbanking/registration', data=data)

                # if not status.is_success(response.status_code):
                #     raise exceptions.ParseError(response.json())

                if contract.vendor.vendor_props.code == 'hanaw':
                    contract.change_status(get_contract_status(type='normal'))
            else:
                Auth.objects.filter(id=self.auth_id).update(is_verified=False, is_expired=True)

            logger.info('ARS auth: {auth} - {reply}, {reply_msg}, {trace_no}, {record:.20s}'
                        .format(**(dict(res_data, **{"auth": self.auth_id}))))
        except Exception as e:
            logger.error(e)

        self.stop()
