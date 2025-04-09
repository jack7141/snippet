import logging
from api.bases.managements.models import Queue, OrderLog
from django.utils import timezone


logger = logging.getLogger(__name__)


class QueueStatus:
    STATUS = ""
    allowed_prev_status = {}
    IS_FINAL_STATUS = True

    def __init__(self, order_queue: Queue):
        self._queue = order_queue
        assert self.STATUS == self._queue.status, "status must be same"
        self.status = self._queue.status

    @property
    def mode(self):
        return self._queue.mode

    @property
    def status_name(self):
        return Queue.STATUS[self._queue.status]

    def handle(self, prev_status):
        if prev_status not in self.allowed_prev_status:
            raise TypeError(
                f"can't transition from {Queue.STATUS[prev_status]} to {self.status_name}"
            )
        logger.info(
            f"{self._queue}: {Queue.STATUS[prev_status]}({prev_status})->{self.status_name}({self.status})"
        )

        if prev_status != self.STATUS and self.IS_FINAL_STATUS:
            self.update_logs(prev_status=prev_status)

    def update_logs(self, prev_status):
        return OrderLog.objects.filter(
            order_id=self._queue.id, status=prev_status
        ).update(status=self.STATUS)


class Pending(QueueStatus):
    STATUS = Queue.STATUS.pending
    IS_FINAL_STATUS = False


class Failed(QueueStatus):
    STATUS = Queue.STATUS.failed
    IS_FINAL_STATUS = True
    allowed_prev_status = {Queue.STATUS.on_hold, Queue.STATUS.processing, STATUS}


class OnHold(QueueStatus):
    STATUS = Queue.STATUS.on_hold
    IS_FINAL_STATUS = False
    allowed_prev_status = {Queue.STATUS.pending}


class Processing(QueueStatus):
    STATUS = Queue.STATUS.processing
    IS_FINAL_STATUS = False
    allowed_prev_status = {Queue.STATUS.on_hold, STATUS}


class Completed(QueueStatus):
    STATUS = Queue.STATUS.completed
    IS_FINAL_STATUS = True
    allowed_prev_status = {Queue.STATUS.processing}

    def update_logs(self, prev_status):
        OrderLog.objects.filter(order_id=self._queue.id, status=prev_status).update(
            status=self.STATUS, concluded_at=timezone.now()
        )


class Canceled(QueueStatus):
    STATUS = Queue.STATUS.canceled
    IS_FINAL_STATUS = True
    allowed_prev_status = {
        Queue.STATUS.pending,
        Queue.STATUS.on_hold,
        Queue.STATUS.processing,
        STATUS,
    }


class Skipped(QueueStatus):
    STATUS = Queue.STATUS.skipped
    IS_FINAL_STATUS = True
    allowed_prev_status = {Queue.STATUS.on_hold}


class QueueStatusContext:
    status_class_map = {
        Queue.STATUS.pending: Pending,
        Queue.STATUS.failed: Failed,
        Queue.STATUS.on_hold: OnHold,
        Queue.STATUS.processing: Processing,
        Queue.STATUS.completed: Completed,
        Queue.STATUS.canceled: Canceled,
        Queue.STATUS.skipped: Skipped,
    }

    def __init__(self, order_queue: Queue):
        self._queue = order_queue
        status_class = self.status_class_map[self._queue.status]
        self._status_instance = status_class(order_queue=self._queue)

    @property
    def status(self):
        return self._status_instance.status

    @property
    def status_name(self):
        return self._status_instance.status_name

    def transition(self, status):
        prev_status = self.status
        status_class = self.status_class_map[status]
        self._queue.status = status
        _status_instance = status_class(order_queue=self._queue)
        _status_instance.handle(prev_status=prev_status)
        self._status_instance = _status_instance
        self._queue.save(update_fields=["status", "note"])
        return self.status
