import logging
import json
from rest_framework import serializers, status
from django.contrib.auth import get_user_model

from api.bases.contracts.models import Contract, ProvisionalContract
from api.bases.orders.models import Order
from api.versioned.v1.contracts.serializers import ContractSerializer
from api.versioned.v1.orders.serializers import OrderCreateSerializer

logger = logging.getLogger('django.server')


class ContractSimpleSerializer(ContractSerializer):
    contract_id = serializers.UUIDField(source='id')

    class Meta:
        model = Contract
        fields = ('contract_id', 'contract_type', 'risk_type',
                  'account_alias', 'reb_required')
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }


class UserContractSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='profile.name', read_only=True, help_text='유저명')
    ci = serializers.CharField(source='profile.get_encrypted_ci', read_only=True)
    contracts = serializers.SerializerMethodField(help_text='유지되고 있는 계약 목록')

    class Meta:
        model = get_user_model()

        fields = ('id', 'name', 'ci', 'contracts',)

        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }

    def get_contracts(self, instance):
        return ContractSimpleSerializer(
            [item for item in instance.contract_set.all() if item.is_canceled is False], many=True).data


class VendorContractSerializer(ContractSerializer):
    name = serializers.CharField(source='user.profile.name', read_only=True, help_text='유저명')
    ci = serializers.CharField(source='user.profile.get_encrypted_ci', read_only=True)

    class Meta:
        model = ContractSerializer.Meta.model
        error_status_codes = ContractSerializer.Meta.error_status_codes
        fields = ('id', 'name', 'ci', 'account_alias', 'contract_type', 'risk_type', 'reb_required')


class VendorOrderSerializer(serializers.ModelSerializer):
    c_id = serializers.PrimaryKeyRelatedField(source='order_item', queryset=Contract.objects.all())
    status = serializers.IntegerField(default=Order.STATUS.processing)

    class Meta:
        model = Order
        fields = ('c_id', 'mode', 'status')

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


class VendorTokenReqSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="profile.name", help_text="성명")
    phone = serializers.CharField(source="profile.phone", help_text="연락처")
    birth = serializers.DateField(source="profile.birth_date", format='%Y%m%d', help_text="생년월일")
    ci_valu = serializers.CharField(source="profile.ci", help_text="CI값")

    class Meta:
        model = get_user_model()
        fields = ('name', 'ci_valu', 'phone', 'birth')


class VendorTokenRespSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="Vendor Token")

    def to_internal_value(self, data):
        return data.get('dataBody', {})



class ExchangeRateRespSeiralizer(serializers.Serializer):
    currency_code = serializers.CharField(help_text="거래통화", source='dataBody.currency_code')
    exchange_rate = serializers.FloatField(help_text="고시환율", source='dataBody.exchange_rate')

    def to_representation(self, instance):
        return super(ExchangeRateRespSeiralizer, self).to_representation(instance)


class ExchangeRateReqSeiralizer(serializers.Serializer):
    pass
