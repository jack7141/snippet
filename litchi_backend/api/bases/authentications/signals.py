from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from api.bases.sms.models import ScTran
from .models import Auth

from common.decorators import disable_for_loaddata

SMS_COMPANY_NAME = settings.SMS_COMPANY_NAME


@receiver(post_save, sender=Auth)
@disable_for_loaddata
def create_user_info(sender, instance, created, **kwargs):
    if created:
        if instance.cert_type == '1':
            msg = '[{}] 인증번호 [{}]를 입력해주세요.'.format(SMS_COMPANY_NAME, instance.code)
            ScTran.objects.create(tr_msg=msg, tr_phone=instance.etc_1)
