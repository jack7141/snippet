import logging
import json
from rest_framework import serializers, status

from django.contrib.auth import get_user_model

from api.bases.orders.models import Order
from api.bases.contracts.models import Contract, ReservedAction, ContractType, ProvisionalContract
from api.bases.contracts.mixins import RebalancingMixin
from api.bases.notifications.models import Topic

from api.versioned.v1.orders.serializers import OrderSerializer
from api.versioned.v1.admin.contracts.serializers import ContractSimpleSerializer
from common.exceptions import PreconditionFailed

logger = logging.getLogger('django.server')


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='profile.name')

    class Meta:
        model = get_user_model()
        fields = ('id', 'email', 'name')


class AdminOrderSerializer(OrderSerializer):
    order_item = ContractSimpleSerializer(help_text="계약사항")
    order_rep = UserSerializer(help_text="주문 처리 계정")
    user = UserSerializer(help_text="고객")


class ShinhanOrderSerializer(serializers.Serializer):
    tmp_acct_no = serializers.CharField(source="account_alias")
    status = serializers.CharField()


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('order_item', 'status', 'mode', 'user')

    def validate(self, attrs):
        contract = attrs.get('order_item', None)
        logger.info('order request from : {user} - data: {data}'.format(user=self.context.get('request').user,
                                                                        data=attrs))
        if contract and contract.user and contract.vendor:
            attrs.update({
                'order_rep': contract.vendor,
                'user': contract.user
            })

            if attrs.get('mode', None) == Order.MODES.new_order and contract.orders.exists():
                raise serializers.ValidationError({'mode': '{} mode already exist.'.format(attrs.get('mode'))})

        else:
            raise serializers.ValidationError({'order_item': 'invalid order_item.'})

        return attrs

    def create(self, validated_data):
        status = validated_data.get('status', Order.STATUS.completed)
        completed_status = Order.STATUS.completed

        if validated_data.get('status', None):
            del validated_data['status']

        prev_instance = Order.objects.filter(completed_at__isnull=True).filter(**validated_data).order_by('created_at')

        if prev_instance.exists() and prev_instance.last().status != completed_status:
            instance = prev_instance.last()
            instance.status = status
            instance.save()
        else:
            mode = validated_data.get('mode',
                                      Order.MODES.rebalancing if prev_instance.exists() else Order.MODES.new_order)
            instance = Order.objects.create(**dict({'mode': mode, 'status': status, **validated_data}))

            if instance.order_item.rebalancing:
                instance.order_item.rebalancing = False
                instance.order_item.save(update_fields=['rebalancing'])

        logger.info('order processed : {id} {mode} {status}'.format(id=instance.id,
                                                                    mode=instance.mode,
                                                                    status=instance.status))

        prov_inst = ProvisionalContract.objects.filter(user=validated_data.get('user'),
                                                       contract_type=validated_data.get('order_item').contract_type,
                                                       is_contract=False)

        if prov_inst.exists():
            prov = prov_inst.get()
            try:
                step_dict = json.loads(prov.step)
            except Exception as e:
                step_dict = {}

            step_dict['name'] = 'order-complete'

            prov.step = json.dumps(step_dict)
            prov.save()

        return instance


class AdminBulkOrderSerializer(serializers.Serializer):
    items = ShinhanOrderSerializer(many=True)

    def create(self, validated_data):
        conditions = {'0': Order.STATUS.completed, '1': Order.STATUS.failed}

        queryset = Contract.objects.filter(is_canceled=False).distinct()

        for k, v in conditions.items():
            _list = [item['account_alias'] for item in validated_data.get('items') if item['status'] == k]
            _qs = queryset.filter(account_alias__in=_list,
                                  orders__status__in=[Order.STATUS.on_hold,
                                                      Order.STATUS.processing,
                                                      Order.STATUS.pending,
                                                      Order.STATUS.failed])
            if _qs.exists():
                _serializer = OrderCreateSerializer(data=[{'order_item': item.id} for item in _qs], many=True,
                                                    context=self.context)
                _serializer.is_valid(raise_exception=True)
                _serializer.save(status=v)

        return validated_data


class FakeRebResponseSerializer(serializers.Serializer):
    contracts = serializers.ListField()


class AdminRebalancingSerializer(serializers.Serializer):
    skip_save = serializers.BooleanField(required=False, default=False, help_text='리밸런싱 저장 로직 패스 여부(default:false)')
    skip_send = serializers.BooleanField(required=False, default=False, help_text='알람 발생 여부(default:false)')
    force_send = serializers.BooleanField(required=False, default=False,
                                          help_text='알람 재전송 여부와 관계없이 알람 발생(default:false)')
    ignore_interval = serializers.BooleanField(required=False, default=False,
                                               help_text='리밸런싱 기간 무시(default:false)')


class AdminRebalancingWithNoteSerializer(AdminRebalancingSerializer):
    note = serializers.CharField(required=True)

    class Meta:
        error_status_codes = {
            status.HTTP_412_PRECONDITION_FAILED: None,
            status.HTTP_428_PRECONDITION_REQUIRED: None
        }


class AdminRebalancingNotifySerializer(serializers.ModelSerializer):
    skip_save = serializers.BooleanField(required=False, default=False, write_only=True)
    skip_send = serializers.BooleanField(required=False, default=False, write_only=True)
    force_send = serializers.BooleanField(required=False, default=False, write_only=True)

    class Meta:
        model = Contract
        fields = ('id', 'contract_number', 'contract_type', 'account_alias', 'reb_required', 'reb_status',
                  'skip_save', 'skip_send', 'force_send')
        extra_kwargs = {
            'contract_type': {'read_only': True},
            'account_alias': {'read_only': True},
        }


class AdminForceRebalancingSerializer(RebalancingMixin,
                                      serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = '__all__'
        error_status_codes = {
            status.HTTP_412_PRECONDITION_FAILED: None
        }

    def is_valid(self, raise_exception=False):
        if super().is_valid(raise_exception=raise_exception):
            if not self.instance.check_condition:
                raise PreconditionFailed(detail=self.instance.reb_status)
            return True
        return False

    def save(self, **kwargs):
        topic = Topic.objects.get(name='notification')
        self.rebalancing_instance(self.instance, topic, force_send=True)
        return self.instance


class AdminOrderSimpleSerializer(serializers.ModelSerializer):
    contract_type = serializers.CharField(source='order_item.contract_type')

    class Meta:
        model = Order
        fields = ('id', 'mode', 'created_at', 'completed_at', 'status', 'contract_type')


class AdminRebalancingGroupSerializer(serializers.ModelSerializer):
    orders = AdminOrderSimpleSerializer(many=True)
    name = serializers.CharField(source='profile.name')

    class Meta:
        model = get_user_model()
        fields = ('id', 'email', 'name', 'orders',)


class AdminReservedActionSerializer(serializers.Serializer):
    notified_count = serializers.IntegerField(read_only=True)
    result = serializers.ListField(read_only=True)
