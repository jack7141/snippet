import json

from django.db import models
from django.utils import timezone
from model_utils import Choices
from model_utils.fields import StatusField

from api.bases.accounts.models import Account
from common.behaviors import Timestampable
from common.models import JSONField
from common.utils import gen_choice_desc


def get_default_strategies():
    _default_strategies = {
        "minus_ratio_threshold": 0,
        "min_update_seconds": 5 * 60,
        "allow_minus_gross": False,
        "ticks": {
            "sell": 0,
            "sell_pct": 0,
            "buy": 0,
            "buy_pct": 0,
        },
    }
    return json.dumps(_default_strategies)


class Event(Timestampable, models.Model):
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
        ("new_order", "신규"), ("sell", "매도"), ("buy", "매수"), ("rebalancing", "리밸런싱")
    )

    id = models.BigAutoField(primary_key=True)
    account_alias = models.ForeignKey(
        Account, on_delete=models.CASCADE, help_text="계좌번호 별칭"
    )
    status = models.IntegerField(
        choices=STATUS,
        default=STATUS.on_hold,
        help_text=gen_choice_desc("주문상태", STATUS),
    )
    mode = StatusField(
        choices_name="MODES",
        null=False,
        blank=False,
        default=MODES.new_order,
        help_text=gen_choice_desc("주문 종류", MODES),
    )
    portfolio_id = models.BigIntegerField(
        null=True, blank=True, default=None, help_text="주문 요청 포트폴리오 ID"
    )
    completed_at = models.DateTimeField(blank=True, null=True, help_text="주문 처리 완료 일자")

    class Meta:
        ordering = ("-created_at",)
        unique_together = (("account_alias", "created_at"),)
        managed = False

    def process(self):
        if self.status == self.STATUS.on_hold:
            self.status = self.STATUS.processing
            self.save(update_fields=["status"])

    def complete(self):
        if self.status == self.STATUS.processing:
            self.status = self.STATUS.completed
            self.completed_at = timezone.now()
            self.save(update_fields=["status", "completed_at"])


class OrderSetting(models.Model):
    class Meta:
        managed = False

    EMPHASIS_TYPES = Choices(
        ("weight_first", "비중 우선(O(n))"),
        ("optimized_deposit", "예수금 최적화(O(2^n))"),
    )

    name = models.CharField(
        unique=True,
        max_length=128,
        null=False,
        blank=False,
        default="default",
        help_text="설정 별칭",
    )
    strategies = JSONField(
        null=False, blank=False, default=get_default_strategies, help_text="주문 전략"
    )
    min_base = models.IntegerField(default=0, help_text="최소 유지 원금")
    emphasis = models.CharField(
        max_length=100,
        default=EMPHASIS_TYPES.optimized_deposit,
        choices=EMPHASIS_TYPES,
        help_text="주문 수량 결정 로직",
    )

    def __str__(self):
        return f"OrderSetting({self.name}, {self.emphasis})"


class OrderDetail(Timestampable, models.Model):
    ORDER_TYPE = Choices(("1", "BID", "매수"), ("2", "ASK", "매도"))
    RESULT = Choices(
        ("1", "SUCCEED", "성공"),
        ("2", "FAILED", "실패"),
        ("3", "CANCELED", "취소"),
        ("4", "STANDBY", "대기"),
    )

    id = models.BigAutoField(primary_key=True)
    account_alias = models.ForeignKey(
        Account, on_delete=models.CASCADE, help_text="계좌번호 별칭"
    )
    code = models.CharField(null=False, max_length=12, help_text="ISIN 코드")
    type = models.CharField(
        null=False,
        max_length=1,
        help_text=gen_choice_desc("매매 구분", ORDER_TYPE),
        choices=ORDER_TYPE,
    )
    ordered_at = models.DateTimeField(help_text="주문 집행 일시")
    order_price = models.IntegerField(help_text="주문금액(원화)")
    order_price_usd = models.FloatField(null=True, help_text="주문금액(외화)")
    paid_at = models.DateTimeField(null=True, blank=True, help_text="결제 완료 일시")
    paid_price = models.IntegerField(null=True, blank=True, help_text="결제금액(원화 체결가)")
    paid_price_usd = models.FloatField(null=True, help_text="결제금액(외화 체결가)")
    shares = models.IntegerField(null=False, help_text="좌수")
    result = models.CharField(
        null=False,
        max_length=1,
        help_text=gen_choice_desc("체결 구분", RESULT),
        choices=RESULT,
    )

    class Meta:
        ordering = ("-created_at",)
        unique_together = (
            ("account_alias", "ordered_at", "code", "type", "created_at"),
        )
        managed = False
