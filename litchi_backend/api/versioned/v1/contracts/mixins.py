from __future__ import unicode_literals
from django.conf import settings
import logging
from rest_framework import status
from rest_framework.exceptions import NotFound, ParseError

from common.contexts import MessageContextFactory, NotiTopic, NotiStatus, NotiStep
from api.bases.authentications.models import Auth
from api.bases.contracts.contexts import ContractContext
from api.bases.contracts.adapters import fep_adapter, firmbanking_adapter, account_adapter
from api.bases.contracts.models import Contract, get_contract_status, ContractStatus
from api.bases.contracts.choices import ContractTypeChoices
from api.bases.orders.models import Order
from api.bases.notifications.models import Notification, Topic
from api.bases.notifications.choices import NotificationChoices

from common.exceptions import DuplicateAccess, PreconditionFailed


class RegstrationException(ParseError):
    default_code = 'registration_error'


class WithdrawException(ParseError):
    default_code = 'withdraw_error'


class AccountTerminateException(ParseError):
    default_code = 'account_terminate_error'


logger = logging.getLogger('django.server')
ORDER_PROXY_CANCELED_MSG = "이미 해지된 서비스입니다"


class TerminateContractMixin(object):
    def get_withdraw_data(self, instance):
        return firmbanking_adapter.get_withdraw_format(ci=instance.user.profile.ci,
                                                       account_alias=instance.account_alias,
                                                       account_number=instance.account_number,
                                                       birth_date=instance.user.profile.birth_date,
                                                       contract_number=instance.contract_number,
                                                       vendor=instance.vendor.vendor_props.code)

    def withdraw(self, instance):
        try:
            instance.change_status(get_contract_status(type='fee_st_withdraw'))
            data = self.get_withdraw_data(instance)

            if instance.term.field_1 == 'v2' and instance.contract_type == 'OEA':
                response = firmbanking_adapter.request('api/v1/firmbanking/withdraw/monthly', data=data)
            else:
                response = firmbanking_adapter.request('api/v1/firmbanking/withdraw', data=data)

            if not status.is_success(response.status_code):
                raise WithdrawException(response.json())
            else:
                instance.change_status(get_contract_status(type='fee_st_withdraw_s'))
        except RegstrationException as e:
            instance.change_status(get_contract_status(type='fee_st_reg_f1'))
            raise e
        except WithdrawException as e:
            instance.change_status(get_contract_status(type='fee_st_withdraw_f1'))
            raise e
        except Exception as e:
            raise e

    def bankingplus_withdraw(self, instance):
        try:
            data = self.get_withdraw_data(instance)

            response = firmbanking_adapter.request('api/v1/bankingplus/withdraw', data=data)

            if not status.is_success(response.status_code):
                raise WithdrawException(response.json())
        except RegstrationException as e:
            raise e
        except WithdrawException as e:
            raise e
        except Exception as e:
            raise e

    def get_realtime_data(self, instance, field_name):
        return instance.realtime.get(field_name, None) if instance.realtime else None

    def terminate_vendor_proxy(self, instance: Contract):
        vendor_code = instance.vendor.vendor_props.code
        if settings.USE_REALTIME:
            getattr(self, 'terminate_{}_proxy'.format(vendor_code))(instance)
        else:
            # Note: 대외계 실시간 조회 미연결시 로직 추가 구현 필요.
            pass

        instance.change_status(get_contract_status(type='vendor_order_proxy_cancel'))

    @staticmethod
    def terminate_kb_proxy(instance: Contract):
        # 제 3자 정보제공 동의 재신청
        endpoint = f'/api/v1/kb/customer/third-party'
        instance.get_realtime_data('realtime', endpoint)

        # 주문대리인 해지 신청
        endpoint = f'/api/v1/kb/account/order-proxy'
        response = fep_adapter.request(endpoint, data={'acct_no': instance.account_number}, method='DELETE')

        if ORDER_PROXY_CANCELED_MSG in response.text:
            logger.warning(f"order proxy is already canceled, {response.text}")
        elif not status.is_success(response.status_code):
            instance.change_status(get_contract_status(type='vendor_order_proxy_cancel_fail'))
            raise PreconditionFailed(response.json())

    @staticmethod
    def terminate_hanaw_proxy(instance: Contract):
        # 일임등록관리 해지
        endpoint = f"/api/v1/hanaw/discretionary/register"
        instance.get_realtime_data('realtime', endpoint, method="DELETE")

        # 뱅킹플러스 출금이체 계좌 해지
        auth = Auth.objects.filter(
            etc_2=instance.pk,
            cert_type=3,
            is_verified=True,
            is_expired=False).order_by('created_date').last()

        data = firmbanking_adapter.get_register_format(account_number=auth.account_number,
                                                       birth_date=instance.user.profile.birth_date,
                                                       contract_number=instance.contract_number,
                                                       serial_number=auth.etc_3,
                                                       bank_code=auth.bank_code,
                                                       phone=auth.etc_1,
                                                       auth_file=auth.etc_entrypted_text_1)
        firmbanking_adapter.request('api/v1/firmbanking/registration', data=data, method="DELETE")

    @staticmethod
    def terminate_advisory_proxy(instance: Contract):
        if settings.USE_REALTIME:
            # 투자자문계약 해지 신청
            endpoint = "/api/v1/kb/account/advisory"
            data = {
                "customer_pin_number": instance.provisional.user.profile.hpin
            }
            response = instance.get_realtime_data('realtime', endpoint, method="DELETE", **data)

            if not response:
                instance.change_status(get_contract_status(type='vendor_contract_quit_advisory_fail'))
                raise PreconditionFailed(response.json())
        else:
            # Note: 대외계 실시간 조회 미연결시 로직 추가 구현 필요.
            pass

        if instance.is_canceled:
            raise NotFound("already canceled.")
        instance.is_canceled = True
        instance.change_status(get_contract_status(type='canceled'))

    def process_advice_type(self, instance):
        # 주문 완료 내역이 있는 경우
        if instance.orders.filter(status=Order.STATUS.completed, completed_at__isnull=False).exists():
            # 자문 계약 해지 litchi -> firmbanking
            self.withdraw(instance)

        if instance.contract_type.is_orderable is False:
            instance.change_status(get_contract_status(type='vendor_wait_cancel'))
        else:
            try:
                response = account_adapter.request(f'/api/v1/accounts/{instance.account_alias}', method='DELETE')
                if not status.is_success(response.status_code):
                    raise AccountTerminateException(response.json())
            except Exception as e:
                raise e
            # 해지 로직 자문 KB
            self.terminate_advisory_proxy(instance=instance)

    def process_discretion(self, instance, withdraw=True, order_proxy=True):
        # 일임 계약 해지 litchi -> account
        is_account_canceled = False

        if instance.status.code in [
            get_contract_status(type='normal', code=True)
        ]:
            if instance.contract_type.is_bankingplus:
                self.bankingplus_withdraw(instance)

            if instance.orders.exists():  # 주문 있는 정상 계약의 경우, 해지매도
                try:
                    response = account_adapter.request(f'/api/v1/accounts/{instance.account_alias}', method='DELETE')
                    if not status.is_success(response.status_code):
                        raise AccountTerminateException(response.json())

                    account_status = response.json().get('status',
                                                         get_contract_status(type='account_sell_reg', code=True))
                    contract_status = ContractStatus.objects.get(code=account_status)
                    is_account_canceled = contract_status.code == get_contract_status(type='canceled', code=True)
                    if is_account_canceled:
                        instance.is_canceled = True
                        self.terminate_vendor_proxy(instance)
                    instance.change_status(contract_status)
                    if contract_status.code == get_contract_status(type='account_sell_reg', code=True):
                        self.register_sell_reg_notification(instance)
                except Exception as e:
                    raise e
            else:
                # 주문이 없는 계약의 경우, 주문대리인 해지대기
                instance.change_status(get_contract_status(type='vendor_order_proxy_cancel'))

        # 환전 완료 ~ 수수료 수취 단계인 경우
        if instance.status.code in [
            get_contract_status(type='account_exchange_s', code=True),
            get_contract_status(type='fee_st_withdraw', code=True),
            get_contract_status(type='fee_st_withdraw_f1', code=True)
        ]:
            self.withdraw(instance)

        # 수수료 수취 완료 ~ 주문대리인 해지 단계인 경우
        if instance.status.code in [
            get_contract_status(type='fee_st_withdraw_s', code=True),
            get_contract_status(type='vendor_order_proxy_cancel', code=True),
            get_contract_status(type='vendor_order_proxy_cancel_fail', code=True),
            get_contract_status(type='vendor_auth_fail_on_cancel', code=True),
            get_contract_status(type='account_sell_s', code=True)
        ]:
            self.terminate_vendor_proxy(instance)
            instance.is_canceled = True
            instance.change_status(get_contract_status(type='canceled'))

        # 해지 상태인 경우 Account Server에 계좌 해지처리 (account_exchange_s -> canceled)
        # 계약 해지상태 갱신이 Account Server와 동기화 된거면 실행하지 않음
        if instance.status.code == get_contract_status(type='canceled', code=True) and \
                not is_account_canceled:
            try:
                response = account_adapter.request(f'/api/v1/accounts/{instance.account_alias}', method='DELETE')
                if not status.is_success(response.status_code):
                    raise AccountTerminateException(response.json())
            except Exception as e:
                raise e

    def perform_destroy(self, instance):
        if instance.is_canceled:
            raise NotFound("already canceled.")

        if instance.contract_type == 'KBPA' and \
                instance.last_transfer and not instance.last_transfer.is_available_cancel:
            raise NotFound('Transfer has not been canceled')

        if instance.status.code not in (get_contract_status(type='bp_fee_st_reg', code=True),
                                        get_contract_status(type='bp_fee_st_reg_success', code=True),
                                        get_contract_status(type='fee_st_reg', code=True),
                                        get_contract_status(type='fee_st_reg_s', code=True),
                                        get_contract_status(type='fee_st_withdraw', code=True),
                                        get_contract_status(type='fee_st_withdraw_s', code=True),
                                        get_contract_status(type='account_sell_reg', code=True),
                                        get_contract_status(type='vendor_wait_cancel', code=True),
                                        get_contract_status(type='canceled', code=True)):

            # 계좌개설 완료 이전 및 투자자문계약 대기 상태인 경우 해지처리 함.
            if instance.status.code in (get_contract_status(type='vendor_wait_account', code=True),
                                        get_contract_status(type='vendor_wait_account_id_card', code=True),
                                        get_contract_status(type='vendor_upload_doc_fail', code=True),
                                        get_contract_status(type='vendor_contract_transaction_limit_wait', code=True),
                                        get_contract_status(type='vendor_wait_order_proxy', code=True),
                                        get_contract_status(type='vendor_contract_advisory_wait', code=True),
                                        get_contract_status(type='vendor_contract_advisory_fail', code=True),
                                        get_contract_status(type='fractional_share_trading_waiting', code=True),
                                        get_contract_status(type='bp_fee_st_reg_wait', code=True),
                                        get_contract_status(type='KRW_margin_apply_wait', code=True),
                                        get_contract_status(type='KRW_margin_apply_success', code=True)):
                instance.is_canceled = True
                instance.change_status(get_contract_status(type='canceled'))
            elif instance.contract_type.operation_type == ContractTypeChoices.OPERATION_TYPE.D:
                ## 일임
                self.process_discretion(instance)
            else:
                ## 자문
                # 후취인 경우
                if instance.contract_type.fee_type == ContractTypeChoices.FEE_TYPE.post:
                    self.process_advice_type(instance)
                # 선취/무료인 경우
                else:
                    instance.change_status(get_contract_status(type='vendor_wait_cancel'))
        else:
            raise DuplicateAccess(DuplicateAccess(detail="already processing.").get_full_details())

    def register_sell_reg_notification(self, instance):
        Notification.objects.create(
            user=instance.user,
            protocol=NotificationChoices.PROTOCOLS.sms,
            register=instance.vendor,
            topic=Topic.objects.get(name='notification'),
            title="해지 매도 안내",
            message="",
            context=MessageContextFactory(ContractContext).get_context_dic(
                instance=instance, topic=NotiTopic.CONTRACT_CANCELLATION,
                status=NotiStatus.IS_STARTED, step=NotiStep.STEP1)
        )
