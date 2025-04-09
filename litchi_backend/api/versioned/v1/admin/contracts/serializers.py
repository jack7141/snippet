from collections import OrderedDict

from rest_framework import serializers, status
from rest_framework.fields import SkipField
from rest_framework.relations import PKOnlyObject

from django.db.models import Count
from rest_framework.exceptions import NotAuthenticated
from django.contrib.auth import get_user_model
from api.bases.contracts.models import (
    Contract,
    ProvisionalContract,
    Transfer,
    Term,
    get_contract_status,
    ContractStatus
)
from api.bases.orders.models import Order
from api.bases.contracts.choices import ContractTypeChoices

from api.versioned.v1.admin.users.serializers import UserIssuanceSeriaizer
from api.versioned.v1.contracts.serializers import (
    ContractCreateSerializer,
    TermSerializer,
    RebalancingQueueCreateSerializer,
)
from api.versioned.v1.contracts.mixins import TerminateContractMixin


class ContractAdminCreateSerializer(ContractCreateSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.all(), help_text="계약자")


class ContractAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ('id', 'contract_number', 'contract_type', 'risk_type', 'account_alias', 'created_at',
                  'is_canceled', 'account_number', 'user_id')
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }


class ContractSimpleSerializer(serializers.ModelSerializer):
    order = serializers.SerializerMethodField(help_text='주문')

    class Meta:
        model = Contract
        fields = ('id', 'contract_number', 'contract_type', 'risk_type', 'account_alias', 'created_at', 'is_canceled',
                  'order')
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }

    def get_order(self, obj):
        # 쿼리 속도 문제로인해 현재 쿼리를 메모리 캐싱후 내리도록 적용
        dates = [item[0] for item in obj.orders.values_list('created_at')]

        return {
            'first': dates[-1] if dates else None,
            'recent': dates[0] if dates else None
        }


class ContractIssuanceAdminSerializer(serializers.ModelSerializer):
    user = UserIssuanceSeriaizer(help_text="고객")
    contract_type = serializers.CharField(source='contract_type.code')
    start_date = serializers.DateTimeField(source='effective_date')
    securities_company = serializers.CharField(source='vendor.vendor_props.company_name')
    account_number = serializers.CharField()
    signature = serializers.CharField(source='condition.sign')
    term = TermSerializer(read_only=True)

    class Meta:
        model = Contract
        fields = ('id', 'contract_number', 'contract_type', 'user', 'created_at',
                  'start_date', 'account_alias', 'securities_company', 'account_number', 'signature', 'term')


class ContractNotificationAdminSerializer(serializers.ModelSerializer):
    protocol = serializers.CharField()
    template_id = serializers.CharField()

    class Meta:
        model = Contract
        fields = ('protocol', 'template_id')


class UserContractSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='profile.name', read_only=True, help_text='유저명')
    phone = serializers.CharField(source='profile.phone', read_only=True, help_text='전화번호')
    contracts = ContractSimpleSerializer(many=True, source='contract_set', help_text='계약 정보')

    class Meta:
        model = get_user_model()

        fields = ('id', 'email', 'date_joined', 'username', 'phone', 'contracts')

        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }

    @staticmethod
    def get_contract_types(obj):
        return set([q.contract_type for q in obj.contract_set.all() if not q.is_canceled])

    @staticmethod
    def get_contract_linked(obj):
        return set([q.contract_type for q in obj.contract_set.all() if q.is_active])


class _UserSerializer(serializers.Serializer):
    active = serializers.SerializerMethodField(help_text='활성화 유저수')
    inactive = serializers.SerializerMethodField(help_text='비활성화 유저수')

    def get_active(self, obj):
        return obj.filter(is_active=True).count()

    def get_inactive(self, obj):
        return obj.filter(is_active=False).count()


class _ContractSerializer(serializers.Serializer):
    active = serializers.SerializerMethodField(help_text='활성화 계약수')
    inactive = serializers.SerializerMethodField(help_text='비활성화 계약수')
    ordered = serializers.SerializerMethodField(help_text='주문까지 완료한 계약수')
    ordered_canceled = serializers.SerializerMethodField(help_text='주문까지 완료했지만 해지한 계약수')

    def get_active(self, obj):
        return obj.filter(is_canceled=False).count()

    def get_inactive(self, obj):
        return obj.filter(is_canceled=True).count()

    def get_ordered(self, obj):
        return obj.annotate(order_count=Count('contract')).filter(order_count__gte=1).count()

    def get_ordered_canceled(self, obj):
        return obj.annotate(order_count=Count('contract')).filter(is_canceled=True, order_count__gte=1).count()


class _ContractTypeSerializer(serializers.Serializer):
    fund = _ContractSerializer(help_text='펀드')
    etf = _ContractSerializer(help_text='ETF')

    def __init__(self, *args, **kwargs):
        super(_ContractTypeSerializer, self).__init__(*args, **kwargs)

    def to_representation(self, instance):
        ret = OrderedDict()
        fields = self._readable_fields

        for field in fields:
            try:
                if field.field_name == 'fund':
                    attribute = instance.filter(contract_type='FA')
                else:
                    attribute = instance.filter(contract_type='EA')
            except SkipField:
                continue

            check_for_none = attribute.pk if isinstance(attribute, PKOnlyObject) else attribute
            if check_for_none is None:
                ret[field.field_name] = None
            else:
                ret[field.field_name] = field.to_representation(attribute)

        return ret


class _OrderSerializer(serializers.Serializer):
    new_order = serializers.SerializerMethodField(help_text='최초 주문수')
    rebalancing = serializers.SerializerMethodField(help_text='리밸런싱 주문수')

    def get_new_order(self, obj):
        return obj.filter(mode=Order.MODES.new_order).count()

    def get_rebalancing(self, obj):
        return obj.filter(mode=Order.MODES.rebalancing).count()


class UserContractDashboardSerializer(serializers.Serializer):
    users = _UserSerializer(help_text='유저')
    contracts = _ContractTypeSerializer(help_text='계약')
    orders = _OrderSerializer(help_text='주문')


class ProvisionalSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user', read_only=True)

    class Meta:
        model = ProvisionalContract
        fields = '__all__'


class TermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = '__all__'


class DProgSyncSerializer(TerminateContractMixin,
                          serializers.Serializer):
    class SyncItemSerializer(serializers.Serializer):
        account_alias = serializers.CharField(help_text='계좌대체번호')
        status = serializers.IntegerField(help_text='계약 상태')

    items = SyncItemSerializer(many=True)

    def validate(self, attrs):
        account_aliases = [item['account_alias'] for item in attrs.get('items')]
        self.queryset = Contract.objects.filter(
            account_alias__in=account_aliases,
            contract_type__operation_type=ContractTypeChoices.OPERATION_TYPE.D,
            status__in=[
                get_contract_status(type='account_sell_reg', code=True),
                get_contract_status(type='account_sell_f1', code=True),
                get_contract_status(type='account_sell_s', code=True),
                get_contract_status(type='account_exchange_reg', code=True),
                get_contract_status(type='account_exchange_f1', code=True),
                get_contract_status(type='account_exchange_s', code=True),
            ]
        )

        validated_aliases = list(self.queryset.values_list('account_alias', flat=True))
        validated_items = [item for item in attrs.get('items') if item.get('account_alias') in validated_aliases]
        attrs.update({'items': validated_items})
        return attrs

    def create(self, validated_data):
        items = {item.get('account_alias'): item.get('status') for item in validated_data.get('items')}
        result = []

        for instance in self.queryset.iterator():
            try:
                target_status = ContractStatus.objects.get(code=items.get(instance.account_alias))
                instance.change_status(target_status)
                self.process_discretion(instance)

            except:
                pass
            finally:
                result.append(OrderedDict({'account_alias': instance.account_alias, 'status': instance.status.code}))

        return {'items': result}


class RebalancingQueueAdminCreateSerializer(RebalancingQueueCreateSerializer):
    def validate_user(self, user):
        if self.context['request'].user.is_staff or self.context['request'].user.is_staff:
            return True
        else:
            raise NotAuthenticated("Rebalancing request must be required by contract owner")


class RebalancingQueueBatchSummarySerializer(serializers.Serializer):
    skipped = serializers.IntegerField(default=0, help_text="건너뜀 Queue Count")
    completed = serializers.IntegerField(default=0, help_text="완료됨 Queue Count")
    canceled = serializers.IntegerField(default=0, help_text="취소됨 Queue Count")


class TransferBatchSerializer(serializers.ModelSerializer):
    contract = ContractAdminSerializer()

    class Meta:
        model = Transfer
        fields = '__all__'
