from rest_framework import serializers

from api.bases.accounts.models import Account
from api.bases.orders.models import (
    Event, OrderDetail,
)
from common.exceptions import PreconditionFailed


class OrderEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ('status', 'completed_at')

    def validate(self, attrs):
        account_alias = attrs.get('account_alias')
        mode = attrs.get('mode')

        if not mode and Event.objects.filter(account_alias=account_alias, mode=Event.MODES.new_order).exists():
            attrs.update({'mode': Event.MODES.rebalancing})

        return attrs

    def is_valid(self, raise_exception=False):
        if super().is_valid(raise_exception=raise_exception):
            account_alias = self.validated_data.get('account_alias')
            if account_alias.event_set.filter(status__in=[
                Event.STATUS.pending,
                Event.STATUS.on_hold,
                Event.STATUS.processing
            ]).exists() and raise_exception:
                raise serializers.ValidationError({'status': 'this account has in progress order'})
            return True

        return False


class OrderEventCreateSerializer(OrderEventSerializer):
    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ('portfolio_id', 'status', 'completed_at')


class OrderEventUpdatePortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ('status', 'mode', 'account_alias', 'completed_at')

    def is_valid(self, raise_exception=False):
        if super().is_valid(raise_exception=raise_exception):
            if self.instance.status != Event.STATUS.on_hold:
                raise serializers.ValidationError(
                    {"status": f"event is must be on_hold to update portfolio id, "
                               f"instance status: {Event.STATUS[self.instance.status]}"})

            if self.instance.account_alias.status not in [Account.STATUS.normal, Account.STATUS.account_suspension]:
                raise PreconditionFailed(f"Account status must be one of "
                                         f"[{Account.STATUS[Account.STATUS.normal]} or {Account.STATUS[Account.STATUS.account_suspension]}] "
                                         f"to update portfolio_id")
            return True
        return False


class OrderDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderDetail
        fields = '__all__'
