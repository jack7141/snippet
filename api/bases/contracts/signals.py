import logging
import json
from datetime import datetime

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from api.bases.contracts.choices import ContractTypeChoices, TransferChoices
from api.bases.contracts.contexts import ContractContext, TransferContext
from api.bases.contracts.models import Contract, ProvisionalContract, Transfer, get_contract_status
from api.bases.notifications.models import Notification, Topic
from api.bases.notifications.choices import NotificationChoices
from common.decorators import disable_for_loaddata
from common.contexts import MessageContextFactory, NotiTopic, NotiStatus, NotiStep
from common.contexts import format_vendor_acct, acct_masking

logger = logging.getLogger('django.server')

CONTRACT_CANCELED_MSG = "[{contract_type} | {risk_name}] {msg}"
RISK_NAMES = ['안정형', '안정추구형', '중립형', '성장형', '공격형']


@receiver(post_save, sender=Contract)
@disable_for_loaddata
def send_transition(sender, instance, created, **kwargs):
    if created:
        try:
            # Note: 하위 버전 호환을 위해 try 문은 남겨둠. 임시계약 데이터가 전체 마이그레이션 되면 해당 코드는 삭제하고 except 부분만 사용
            pv = ProvisionalContract.objects.get(user=instance.user,
                                                 contract_type=instance.contract_type,
                                                 is_contract=False)
            pv.contract = instance
            pv.save(update_fields=['contract'])

        except ProvisionalContract.DoesNotExist:
            pv = ProvisionalContract.objects.get_or_create(
                user=instance.user,
                contract_type=instance.contract_type,
                contract=instance
            )

    if instance.status.code == get_contract_status(type='canceled', code=True) and not instance.canceled_at:
        instance.canceled_at = timezone.now()
        instance.save(update_fields=['canceled_at'])

        if instance.contract_number == instance.account_number == instance.account_alias:
            return

        acct_no = format_vendor_acct(
            vendor_acct=acct_masking(acct_no=instance.account_number),
            vendor_code=instance.vendor.vendor_props.code
        )
        contract_type = instance.contract_type.name
        operation_type_name = ContractTypeChoices.OPERATION_TYPE[instance.contract_type.operation_type]
        vendor_props = instance.vendor.vendor_props
        msg = "{operation_type_name} 해지 완료. {terminate_msg} {company_name} {acct_no}".format(
            operation_type_name=operation_type_name if instance.risk_type is not None else ' 계약',
            terminate_msg=vendor_props.terminate_msg,
            company_name=vendor_props.company_name,
            acct_no=acct_no)

        if instance.risk_type is not None:
            msg = CONTRACT_CANCELED_MSG.format(contract_type=contract_type,
                                               risk_name=RISK_NAMES[instance.risk_type],
                                               msg=msg)

        Notification.objects.create(
            user=instance.user,
            protocol=NotificationChoices.PROTOCOLS.sms,
            register=instance.vendor,
            topic=Topic.objects.get(name='notification'),
            title="계약 해지 안내",
            message=msg,
            context=MessageContextFactory(ContractContext).get_context_dic(
                instance=instance, topic=NotiTopic.CONTRACT_CANCELLATION,
                status=NotiStatus.IS_COMPLETE, step=NotiStep.STEP1)
        )

        try:
            pv_instance = ProvisionalContract.objects.get(user=instance.user,
                                                          contract_type=instance.contract_type,
                                                          is_contract=False)
            pv_instance.is_contract = True
            pv_instance.save()
        except ProvisionalContract.DoesNotExist:
            pass

    if instance.status.code == get_contract_status(type='vendor_wait_account', code=True) and not \
            (instance.contract_number == instance.account_number == instance.account_alias):
        Notification.objects.create(
            user=instance.user,
            protocol=NotificationChoices.PROTOCOLS.sms,
            register=instance.vendor,
            topic=Topic.objects.get(name='notification'),
            title="계좌 개설 안내",
            message="",
            context=MessageContextFactory(ContractContext).get_context_dic(
                instance=instance, topic=NotiTopic.ACCOUNT_OPENED, status=NotiStatus.IS_COMPLETE, step=NotiStep.STEP1)
        )
        if instance.contract_type.operation_type == ContractTypeChoices.OPERATION_TYPE.D:
            instance.status = get_contract_status(type='vendor_wait_order_proxy')
        else:
            if instance.contract_type.is_orderable and \
                    instance.contract_type.operation_type == ContractTypeChoices.OPERATION_TYPE.A:
                instance.status = get_contract_status(type='vendor_contract_advisory_wait')
            else:
                instance.status = get_contract_status(type='normal')

        instance.acct_completed_at = timezone.now()
        instance.save(update_fields=['status', 'acct_completed_at'])

    if instance.status.code == get_contract_status(type='vendor_account_success', code=True):
        Notification.objects.create(
            user=instance.user,
            protocol=NotificationChoices.PROTOCOLS.sms,
            register=instance.vendor,
            topic=Topic.objects.get(name='notification'),
            title="계좌 개설 안내",
            message="",
            context=MessageContextFactory(ContractContext).get_context_dic(
                instance=instance, topic=NotiTopic.ACCOUNT_OPENED, status=NotiStatus.IS_COMPLETE, step=NotiStep.STEP1)
        )

        instance.status = get_contract_status(type='vendor_upload_doc_fail')
        instance.acct_completed_at = timezone.now()
        instance.save(update_fields=['status', 'acct_completed_at'])


@receiver(post_save, sender=ProvisionalContract)
@disable_for_loaddata
def update_profile(sender, instance, created, **kwargs):
    try:
        if not instance.step:
            return
        step = json.loads(instance.step)
        data = step.get('data')

        if data:
            name = data.get('username')
            ssn = data.get('ssn')
            tel = data.get('tel')
            birth_date = ssn[:6]
            gender_code = ssn[6]

            year_prefix = 19

            if gender_code in ['0', '9']:
                year_prefix -= 1
            elif gender_code in ['3', '4', '7', '8']:
                year_prefix += 1

            profile = instance.user.profile

            profile.name = name
            profile.birth_date = datetime.strptime(str(year_prefix) + birth_date, '%Y%m%d')
            profile.gender_code = gender_code
            profile.phone = tel

            profile.save(update_fields=['name', 'birth_date', 'gender_code', 'phone'])
    except json.JSONDecodeError:
        pass
    except Exception as e:
        logger.warning(e)


@receiver(post_save, sender=Transfer)
@disable_for_loaddata
def send_transfer(sender, instance: Transfer, created, **kwargs):
    # Note: 연금 이전 신청 시 발송하는 메시지
    acct_no = instance.contract.account_number
    vendor = instance.contract.vendor.vendor_props
    opponent_acct_no = instance.account_number
    opponent_vendor = instance.vendor

    msg_format = "{opponent_vendor}({opponent_acct_no}) -> {vendor}({acct_no})".format(
        opponent_vendor=opponent_vendor,
        opponent_acct_no=acct_masking(acct_no=opponent_acct_no),
        vendor=vendor.company_name,
        acct_no=format_vendor_acct(
            vendor_acct=acct_masking(acct_no=acct_no),
            vendor_code=vendor.code
        )
    )

    # Note: KB 연금 이전 신청 즉시 고객에게 발송되는 메시지
    if created:
        msg = "KB연금이전 신규 - " + msg_format

        Notification.objects.create(
            user=instance.contract.user,
            protocol=NotificationChoices.PROTOCOLS.sms,
            register=instance.contract.vendor,
            topic=Topic.objects.get(name='notification'),
            title="KB연금이전 신규",
            message=msg,
            context=MessageContextFactory(TransferContext).get_context_dic(
                instance=instance, topic=NotiTopic.ACCOUNT_TRANSFER,
                status=NotiStatus.IS_STARTED, step=NotiStep.STEP1)
        )

    # Note: KB 연금 이전이 '성공'일 경우 고객에게 발송되는 메시지
    if instance.status == TransferChoices.STATUS.transfer_done and not instance.is_canceled:
        msg = "KB연금이전 성공 - " + msg_format

        Notification.objects.create(
            user=instance.contract.user,
            protocol=NotificationChoices.PROTOCOLS.sms,
            register=instance.contract.vendor,
            topic=Topic.objects.get(name='notification'),
            title="KB연금이전 성공",
            message=msg,
            context=MessageContextFactory(TransferContext).get_context_dic(
                instance=instance, topic=NotiTopic.ACCOUNT_TRANSFER,
                status=NotiStatus.IS_COMPLETE, step=NotiStep.STEP1)
        )

    # Note: KB 연금 이전이 '실패'일 경우 고객에게 발송되는 메시지
    if instance.status in [TransferChoices.STATUS.transfer_fail, TransferChoices.STATUS.transfer_auto_fail] \
            and not instance.is_canceled:
        msg = "KB연금이전 실패 - " + msg_format

        Notification.objects.create(
            user=instance.contract.user,
            protocol=NotificationChoices.PROTOCOLS.sms,
            register=instance.contract.vendor,
            topic=Topic.objects.get(name='notification'),
            title="KB연금이전 신청 실패",
            message=msg,
            context=MessageContextFactory(TransferContext).get_context_dic(
                instance=instance, topic=NotiTopic.ACCOUNT_TRANSFER,
                status=NotiStatus.IS_CANCELED, step=NotiStep.STEP1)
        )
