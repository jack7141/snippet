import pytz

from api.bases.accounts.models import Account, AssetDetail, Asset
from api.versioned.v1.accounts.serializers import AssetDetailSerializer
from api.bases.managements.models import OrderLog
from rest_framework import serializers
from api.bases.orders.models import Event
from api.versioned.v1.orders.serializers import EventSerializer
from api.bases.managements.models import Queue, ErrorOccur
from common.utils import get_local_today


class ErrorParamSerializer(serializers.Serializer):
    is_error_alive = serializers.NullBooleanField(required=False)
    error_ids = serializers.CharField(required=False)
    account_alias = serializers.CharField(required=False)


class ErrorOccurSerializer(serializers.ModelSerializer):
    solved_at = serializers.ReadOnlyField(source="errorsolved.solved_at")
    response_manual = serializers.ReadOnlyField(source="error.response_manual")
    error_msg = serializers.ReadOnlyField(source="error.error_msg")
    order_note = serializers.ReadOnlyField(source="order.note")

    class Meta:
        model = ErrorOccur
        fields = (
            "account_alias",
            "occured_at",
            "error_id",
            "solved_at",
            "error_msg",
            "order_note",
            "response_manual",
        )

    def to_representation(self, instance):
        occured_at_kst = instance.occured_at.astimezone(
            pytz.timezone("Asia/Seoul")
        ).strftime("%Y-%m-%d")
        solved_at_kst = (
            instance.errorsolved.solved_at.astimezone(
                pytz.timezone("Asia/Seoul")
            ).strftime("%Y-%m-%d")
            if hasattr(instance, "errorsolved")
            else None
        )
        account_prev_asset = list(
            Asset.objects.filter(
                account_alias=instance.account_alias, created_at__lte=occured_at_kst
            ).order_by("-created_at")
        )[:2]
        if len(account_prev_asset) == 0:
            base, deposit, balance = "-", "-", "-"
        else:
            account_prev_asset = account_prev_asset[-1]
            base, deposit, balance = (
                account_prev_asset.base,
                account_prev_asset.deposit,
                account_prev_asset.balance,
            )
        res = super().to_representation(instance)
        res.update({"occured_at": occured_at_kst})
        res.update({"solved_at": solved_at_kst})
        res.update({"error_prev_base": base})
        res.update({"error_prev_total_asset": deposit + balance})
        return res


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = "__all__"


class OrderLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLog
        fields = "__all__"

    account_alias = serializers.CharField(source="order.account_alias")


class QueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Queue
        fields = "__all__"

    order_basket = serializers.JSONField(help_text="OrderBasket")

    def to_representation(self, instance):
        representation = super(QueueSerializer, self).to_representation(instance)

        order_logs = OrderLog.objects.filter(order=instance)
        order_log_serializer = OrderLogSerializer(order_logs, many=True)
        representation["logs"] = order_log_serializer.data
        return representation


class OrderBasketRowSerializer(serializers.Serializer):
    code = serializers.CharField(help_text="종목코드")
    shares = serializers.IntegerField(help_text="목표수량")
    new_shares = serializers.IntegerField(help_text="주문수량")
    krw_price = serializers.IntegerField(min_value=0, help_text="가격(원화)")
    usd_price = serializers.DecimalField(
        min_value=0, decimal_places=2, max_digits=12, help_text="가격(외화)"
    )
    buy_price = serializers.IntegerField(min_value=0, help_text="구매가격(원화)")


class OrderBasketSerializer(serializers.Serializer):
    order_basket = OrderBasketRowSerializer(many=True)
    is_rebalancing_condition_met = serializers.BooleanField()
    account_number = serializers.CharField(help_text="계좌번호")
    base = serializers.FloatField(help_text="투자원금")
    summary = serializers.JSONField(required=False)


class SuspensionAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = "__all__"

    def to_representation(self, instance):
        representation = super(SuspensionAccountSerializer, self).to_representation(
            instance
        )
        events = Event.objects.filter(account_alias=instance.pk)
        event_serializer = EventSerializer(events, many=True)
        representation["events"] = event_serializer.data
        return representation


class SuspensionAccountDetailSerializer(SuspensionAccountSerializer):
    def to_representation(self, instance):
        representation = super(
            SuspensionAccountDetailSerializer, self
        ).to_representation(instance)
        queues = Queue.objects.filter(account_alias=instance.pk).exclude(
            status__in=[Queue.STATUS.skipped]
        )
        queue_serializer = QueueSerializer(queues, many=True)
        representation["queues"] = queue_serializer.data
        asset_details = AssetDetail.objects.filter(
            account_alias=instance.pk, created_at__date=get_local_today().date()
        )
        asset_details_data = []
        if asset_details.exists():
            asset_detail_serializer = AssetDetailSerializer(asset_details, many=True)
            asset_details_data = asset_detail_serializer.data
        representation["asset_details"] = asset_details_data
        return representation
