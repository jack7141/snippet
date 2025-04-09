from django.db import models
from django.utils import timezone
from fernet_fields import EncryptedCharField
from model_utils import Choices

from common.behaviors import Timestampable
from common.decorators import reversion_diff
from common.utils import gen_choice_desc


def create_account_alias():
    return timezone.now().strftime("%Y%m%d%H%M%S%f")


class Account(Timestampable, models.Model):
    class Meta:
        managed = False

    RISK_TYPE = Choices(
        (0, "VERY_LOW", "초저위험"),
        (1, "LOW", "저위험"),
        (2, "MID", "중위험"),
        (3, "HIGH", "고위험"),
        (4, "VERY_HIGH", "초고위험"),
    )
    STRATEGY_CODE = Choices(
        (0, "STANDARD", "성장 테마형"),
        (1, "INCOME", "배당 테마형"),
        (2, "ASSET_ALLOCATION", "자산 배분형"),
        (90, "ACA", "ACA"),  # Active Combined Asset Strategy
        (91, "BL", "BL"),  # Black-Litterman
        (92, "PAA", "PAA"),  # Protective Asset Allocation
        (93, "MVO", "MVO"),  # Mean Variance Optimization
        (94, "VAA", "VAA"),  # Vigilant Asset Allocation
    )
    ACCOUNT_TYPE = Choices(
        ("kr_fund", "국내 펀드"), ("kr_etf", "국내 ETF"), ("etf", "해외 ETF")
    )
    STATUS = Choices(
        (0, "canceled", "해지됨"),
        (1, "normal", "정상 유지"),
        (22, "account_sell_reg", "해지 매도 진행 중"),
        (23, "account_sell_f1", "해지 매도 실패"),
        (24, "account_sell_s", "해지 매도 완료"),
        (25, "account_exchange_reg", "환전 진행 중"),
        (26, "account_exchange_f1", "환전 실패"),
        (27, "account_exchange_s", "환전 완료"),
        (3, "account_suspension", "운용 중지"),
        (31, 'unsupported_suspension', '미지원 종목 보유 운용 중지'),
        (32, 'base_amount_suspension', '최소 원금 위반 중지'),
        (33, 'trade_suspension', '임의 거래 중지'),
        (34, 'risk_type_suspension', '투자 성향 안정형 운용 중지'),
    )

    account_alias = models.CharField(
        primary_key=True,
        default=create_account_alias,
        max_length=128,
        editable=False,
        help_text="계좌번호 별칭(INDEX)",
    )
    vendor_code = models.CharField(null=False, max_length=8, help_text="증권사구분")
    account_number = EncryptedCharField(
        null=False, max_length=128, help_text="계좌번호(암호화필수)"
    )
    account_type = models.CharField(
        choices=ACCOUNT_TYPE,
        max_length=8,
        blank=False,
        null=False,
        help_text=gen_choice_desc("자산 구분", ACCOUNT_TYPE),
    )
    status = models.IntegerField(
        choices=STATUS, default=STATUS.normal, help_text="계약 상태"
    )
    risk_type = models.IntegerField(
        choices=RISK_TYPE, null=True, blank=True, help_text="투자성향"
    )
    deleted_at = models.DateTimeField(
        null=True, blank=True, editable=False, default=None, help_text="삭제 요청 일자"
    )
    order_setting = models.ForeignKey(
        "orders.OrderSetting",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="주문 전략 설정",
    )
    strategy_code = models.IntegerField(
        choices=STRATEGY_CODE, null=True, blank=True, help_text="전략"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_fields = {}
        self.set_init_fields()

    def __str__(self):
        return f"{self.account_number}({self.vendor_code})"

    @reversion_diff
    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
        self.set_init_fields()

    def set_init_fields(self):
        for _field in self._meta.fields:
            self._init_fields[_field.name] = getattr(self, _field.name)

    def update_status(self, status: int) -> None:
        self.status = status
        self.save(update_fields=["status"])


class Asset(Timestampable, models.Model):
    id = models.BigAutoField(primary_key=True)
    account_alias = models.ForeignKey(
        Account, on_delete=models.CASCADE, help_text="계좌번호 별칭"
    )
    base = models.IntegerField(null=False, help_text="투자원금(KRW)")
    deposit = models.IntegerField(null=False, help_text="예수금(KRW)")
    balance = models.IntegerField(null=False, help_text="평가금(KRW)")
    prev_deposit = models.IntegerField(null=False, help_text="전일자 예수금(KRW)")
    base_usd = models.FloatField(null=False, help_text="투자원금(USD)")
    deposit_usd = models.FloatField(null=False, help_text="예수금(USD)")
    balance_usd = models.FloatField(null=False, help_text="평가금(USD)")

    class Meta:
        unique_together = (("account_alias", "created_at"),)
        managed = False


class AssetDetail(Timestampable, models.Model):
    id = models.BigAutoField(primary_key=True)
    account_alias = models.ForeignKey(
        Account, on_delete=models.CASCADE, help_text="계좌번호 별칭"
    )
    code = models.CharField(null=False, max_length=12, help_text="ISIN 코드")
    shares = models.IntegerField(null=False, help_text="좌수")
    buy_price = models.IntegerField(null=False, help_text="매수금(KRW)")
    balance = models.IntegerField(null=False, help_text="평가금(KRW)")
    buy_price_usd = models.FloatField(null=False, help_text="매수금(USD)")
    balance_usd = models.FloatField(null=False, help_text="평가금(USD)")

    class Meta:
        unique_together = (("account_alias", "code", "created_at"),)
        managed = False
