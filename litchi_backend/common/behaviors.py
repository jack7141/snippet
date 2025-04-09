import uuid

from django.db import models


class Timestampable(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')

    class Meta:
        abstract = True


class UniqueTimestampable(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, help_text='생성일')
    updated_at = models.DateTimeField(auto_now=True, help_text='수정일')

    class Meta:
        abstract = True
