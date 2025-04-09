import pytz
from django.db import models
from model_utils.fields import AutoCreatedField, AutoLastModifiedField


class Timestampable(models.Model):
    created_at = AutoCreatedField(help_text='생성일')
    updated_at = AutoLastModifiedField(help_text='수정일')

    class Meta:
        abstract = True

    @property
    def created_at_kst(self):
        return self.created_at.astimezone(pytz.timezone('Asia/Seoul'))
