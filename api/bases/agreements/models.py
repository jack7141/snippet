import uuid

from django.db import models
from django.conf import settings
from api.bases.contracts.models import validate_file_extension
from django.core.exceptions import ValidationError


class AgreementGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(max_length=128, blank=False, null=False, help_text='동의 조건 이름')
    is_default = models.BooleanField(default=False, help_text='기본 동의 조건 여부')
    is_publish = models.BooleanField(default=False, help_text='발행 여부')
    created_at = models.DateTimeField(auto_now_add=True, help_text='동의 타입 생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='동의 타입 수정일')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.title and self.is_default:
            try:
                agreement_group = AgreementGroup.objects.filter(title=self.title).get(is_default=True)
                if self != agreement_group:
                    agreement_group.is_default = False
                    agreement_group.title = agreement_group.title + "_" + agreement_group.created_at.strftime("%Y.%m.%d")
                    agreement_group.save()

                    try:
                        types = Type.objects.filter(agreement_group=agreement_group)
                        if types.exists():
                            for type in types:
                                type.code = type.code + "_" + agreement_group.created_at.strftime("%Y.%m.%d")
                                type.save()
                    except Type.DoesNotExist:
                        pass
            except AgreementGroup.DoesNotExist:
                pass
        super(AgreementGroup, self).save(*args, **kwargs)


def get_agreement_group_default_title():
    return AgreementGroup.objects.get(title="-").id


class Type(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    agreement_group = models.ForeignKey(AgreementGroup, on_delete=models.PROTECT,
                                        related_name='types', help_text='각 동의서 리스트',
                                        default=get_agreement_group_default_title)
    code = models.CharField(max_length=60, blank=False, null=False, help_text='동의 타입 코드')
    name = models.CharField(max_length=60, blank=False, null=False, help_text='동의 타입명')
    description = models.TextField(blank=True, null=True, help_text='동의 타입 설명')
    is_required = models.BooleanField(default=False, help_text='동의 필수 여부 true:필수 false:선택')
    exp_days = models.PositiveIntegerField(default=0, blank=False, null=False, help_text='동의 유효 일수')
    agreement_file = models.FileField(upload_to='agreements/%Y%m%d', validators=[validate_file_extension],
                                      blank=True, null=True, help_text='동의서 파일')
    created_at = models.DateTimeField(auto_now_add=True, help_text='동의 타입 생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='동의 타입 수정일')

    def __str__(self):
        return self.code + ' | ' + self.name

    def clean(self, *args, **kwargs):
        if self.code:
            codes = Type.objects.values_list("code", flat=True)
            if self.code in codes:
                raise ValidationError('The code already exists')
        super().save(*args, **kwargs)

    class Meta:
        unique_together = (('id', 'code'),)


class Agreement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    agreement_group = models.ForeignKey(AgreementGroup, on_delete=models.PROTECT, related_name='agreement',
                                        help_text='동의 타입 그룹', default=get_agreement_group_default_title)
    type = models.ForeignKey(Type, on_delete=models.PROTECT, related_name='agreement', help_text='동의 타입')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agreement',
                             help_text='유저')
    created_at = models.DateTimeField(auto_now_add=True, help_text='동의 일시')
