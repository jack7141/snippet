import json
from django.db import models
from model_utils.choices import Choices
from model_utils.fields import StatusField
from model_utils.models import TimeStampedModel

from common.behaviors import StatusCheckable
from common.decorators import cached_property
from api.bases.accounts.models import Account
from common.models import JSONField
from common.utils import gen_choice_desc
from common.utils import get_local_today
import pandas as pd
from datetime import datetime
from typing import List
from django.utils import timezone

# Create your models here.
ASK = "01"
BID = "02"

MAX_NOTE_SIZE = 120


class Queue(StatusCheckable, TimeStampedModel):
    STATUS = Choices(
        (1, "pending", "지연중"),
        (2, "failed", "실패"),
        (3, "on_hold", "대기중"),
        (4, "processing", "진행중"),
        (5, "completed", "완료됨"),
        (6, "canceled", "취소됨"),
        (7, "skipped", "건너뜀"),
    )

    MODES = Choices(
        ("sell", "매도청산"),
        ("bid", "매수"),
        ("ask", "매도"),
    )

    account_alias = models.CharField(
        max_length=128, editable=False, help_text="계좌번호 별칭(INDEX)", db_index=True
    )
    vendor_code = models.CharField(null=True, max_length=8, help_text="증권사구분", db_index=True)

    status = models.SmallIntegerField(
        choices=STATUS,
        default=STATUS.on_hold,
        help_text=gen_choice_desc("주문 종류", STATUS),
    )
    management_at = models.DateTimeField(editable=False, default=get_local_today)
    mode = StatusField(
        choices_name="MODES",
        null=False,
        blank=False,
        default=MODES.bid,
        help_text=gen_choice_desc("주문 종류", MODES),
    )
    portfolio_id = models.CharField(max_length=20, null=True, blank=True)
    note = models.CharField(max_length=128, null=True, blank=True, help_text="예외사항 정보")
    order_basket = JSONField(
        null=True, editable=False, blank=True, default="", help_text="OrderBasket"
    )

    def set_order_basket(self, order_basket, note=""):
        if isinstance(order_basket, pd.DataFrame):
            if self.mode == self.MODES.bid:
                order_basket = order_basket[order_basket.new_shares > 0]
            elif self.mode in [self.MODES.ask, self.MODES.sell]:
                order_basket = order_basket[order_basket.new_shares < 0]
            else:
                raise KeyError(f"Unsupported mode({self.mode})")

            if order_basket.empty:
                self.status = Queue.STATUS.skipped
                if self.mode == self.MODES.sell:
                    note = "기청산된 주문"
            else:
                self.status = Queue.STATUS.on_hold

                self.order_basket = json.dumps(
                    order_basket.reset_index().to_dict(orient="records")
                )
        else:
            self.status = Queue.STATUS.canceled

        if note:
            self.note = note[:MAX_NOTE_SIZE]

    def __str__(self):
        return f"Queue({self.id}, {self.STATUS[self.status]}, {self.MODES[self.mode]})"

    @cached_property
    def account(self):
        return Account.objects.get(account_alias=self.account_alias)

    @property
    def is_account_being_closed(self):
        # 주문이 sell 모드이고, 계좌의 상태가 해지 매도 중 혹은 해지 매도 실패인 경우
        return self.mode == Queue.MODES.sell and self.account.status in [
            Account.STATUS.account_sell_reg,
            Account.STATUS.account_sell_f1,
        ]

    def save(self, portfolio_id=None, *args, **kwargs):
        if not self.id:
            # self.portfolio_id = self.account.portfolio_id
            self.portfolio_id = (
                portfolio_id if portfolio_id is not None else self.account.risk_type
            )
        return super().save(*args, **kwargs)


class OrderLogManager(models.Manager):
    def complete_executed_orders(self, order_queue_id, unexecuted_codes: List[str]):
        executed_order_logs = self.filter(
            order_id=order_queue_id, status=OrderLog.STATUS.processing
        ).exclude(code__in=unexecuted_codes)
        executed_order_logs.update(
            status=OrderLog.STATUS.completed, concluded_at=timezone.now()
        )


class OrderLog(StatusCheckable, TimeStampedModel):
    objects = OrderLogManager()
    TYPE = Choices(
        (
            "Bid",
            [
                (10, "BID_REGISTER", "매수 신청"),
                (11, "BID_AMEND", "매수 정정"),
                (12, "BID_CANCEL", "매수 취소"),
            ],
        ),
        (
            "Ask",
            [
                (20, "ASK_REGISTER", "매도 신청"),
                (21, "ASK_AMEND", "매도 정정"),
                (22, "ASK_CANCEL", "매도 취소"),
            ],
        ),
    )
    STATUS = Choices(
        (1, "pending", "지연중"),
        (2, "failed", "실패"),
        (3, "on_hold", "대기중"),
        (4, "processing", "진행중"),
        (5, "completed", "완료됨"),
        (6, "canceled", "취소됨"),
        (7, "skipped", "건너뜀"),
    )
    order = models.ForeignKey(
        Queue, on_delete=models.CASCADE, related_name="order_logs"
    )
    code = models.CharField(null=True, blank=True, max_length=12, help_text="ISIN 코드")
    type = models.SmallIntegerField(
        null=True, blank=True, choices=TYPE, help_text="주문 구분"
    )
    status = models.SmallIntegerField(
        null=True, blank=True, choices=STATUS, default=STATUS.processing
    )
    order_no = models.IntegerField(null=True, blank=True, help_text="주문번호")
    order_price = models.FloatField(null=True, blank=True, help_text="주문금액")
    market_price = models.FloatField(null=True, blank=True, help_text="시장가격(15분 지연)")
    ordered_at = models.DateTimeField(null=True, blank=True, help_text="주문 집행 일시")
    concluded_at = models.DateTimeField(null=True, blank=True, help_text="체결 확인 일시")
    currency_code = models.CharField(
        null=True, blank=True, max_length=2, help_text="국가 코드"
    )
    shares = models.PositiveIntegerField(
        null=True, blank=True, default=0, help_text="좌수"
    )
    error_msg = models.CharField(
        max_length=128, null=True, blank=True, help_text="에러 사유"
    )

    def __str__(self):
        return f"OrderLog({self.id},{self.order.account.account_number},{self.TYPE[self.type]},{self.STATUS[self.status]})"

    @cached_property
    def account(self):
        return self.order.account

    @property
    def account_alias(self):
        return self.account.account_alias


class OrderReport(TimeStampedModel):
    REPORT_TYPES = Choices(
        ("00", "monitoring", "주문 모니터링"),
        ("01", "error", "오류"),
        ("02", "anomaly", "이상탐지"),
    )

    order = models.ForeignKey(
        Queue, on_delete=models.CASCADE, related_name="order_report"
    )
    report_type = models.CharField(
        default=REPORT_TYPES.monitoring,
        max_length=4,
        choices=REPORT_TYPES,
        help_text=gen_choice_desc("리포트 종류", REPORT_TYPES),
    )
    title = models.CharField(default="", max_length=200, help_text="주문 리포트")
    body = models.TextField(default="", help_text="본문")
    config = JSONField(default={}, help_text="사용한 설정 값")

    def write_body(self, data, desc=""):
        if desc:
            self.body += f"# {desc} at {datetime.now().isoformat()}\n"

        if isinstance(data, pd.DataFrame):
            self.body += data.to_string(float_format=lambda x: "%.3f" % x) + "\n\n"
        else:
            self.body += str(data) + "\n\n"


class ErrorSet(models.Model):

    ERROR_CODE = Choices(
        (1001, "short_base", "투자금미달"),
        (1002, "unsupported_item", "미지원 종목 보유"),
        (1003, "invalid_transaction", "고객 임의 거래 시도"),
        (1004, "fail_full_short", "해지매도 실패"),
        (1005, "pwd_error", "비밀번호 사고 오류"),
        (2001, "mp_sum", "MP sum 1 오류"),
        (2002, "mp_unaccepted_item", "MP 일임 서비스 금지 종목 포함"),
        (2004, "api_error", "API 작동 오류"),
        (2005, "emphasis_error", "emphasis_ordersetting 확인"),
        (2006, "portfolio_type_error", "portfolio_type확인"),
    )

    error_id = models.IntegerField(
        primary_key=True, choices=ERROR_CODE, help_text="에러 종류"
    )
    error_msg = models.CharField(null=False, max_length=50, help_text="에러 메세지")
    response_manual = models.CharField(null=False, max_length=200, help_text="대응 매뉴얼")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.error_id)


class ErrorOccur(models.Model):
    error_occur_id = models.AutoField(primary_key=True)
    error = models.ForeignKey(
        ErrorSet, on_delete=models.CASCADE, help_text="error_occur_id"
    )
    order = models.ForeignKey(
        Queue, on_delete=models.CASCADE, null=True, related_name="order_id"
    )
    account_alias = models.CharField(
        max_length=128, editable=False, help_text="계좌번호 별칭(INDEX)"
    )
    occured_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.account_alias}({self.error_id})({self.error_occur_id})"


#
class ErrorSolved(models.Model):
    error_occur = models.OneToOneField(
        ErrorOccur,
        primary_key=True,
        on_delete=models.CASCADE,
        verbose_name="error_occur_id",
    )
    solved_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.error_occur_id)
