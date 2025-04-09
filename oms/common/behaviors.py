from django.db import models
from model_utils.fields import AutoCreatedField, AutoLastModifiedField
from model_utils.choices import Choices


class Timestampable(models.Model):
    created_at = AutoCreatedField(help_text="생성일")
    updated_at = AutoLastModifiedField(help_text="수정일")

    class Meta:
        abstract = True


class StatusCheckable:
    STATUS = Choices(
        (1, "pending", "지연중"),
        (2, "failed", "실패"),
        (3, "on_hold", "대기중"),
        (4, "processing", "진행중"),
        (5, "completed", "완료됨"),
        (6, "canceled", "취소됨"),
        (7, "skipped", "건너뜀"),
    )
    status = None

    @property
    def is_pending(self):
        return self.status == self.STATUS.pending

    @property
    def is_failed(self):
        return self.status == self.STATUS.failed

    @property
    def is_on_hold(self):
        return self.status == self.STATUS.on_hold

    @property
    def is_processing(self):
        return self.status == self.STATUS.processing

    @property
    def is_completed(self):
        return self.status == self.STATUS.completed

    @property
    def is_canceled(self):
        return self.status == self.STATUS.canceled

    @property
    def is_skipped(self):
        return self.status == self.STATUS.skipped
