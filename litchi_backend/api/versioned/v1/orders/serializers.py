import logging

from rest_framework import serializers

from api.bases.orders.adapters import ea_oms_adapter
from api.bases.orders.models import Order, OrderDetail
from api.bases.contracts.models import Contract, get_contract_status
from api.bases.contracts.adapters import account_adapter
from api.bases.portfolios.models import PortfolioDaily
from api.bases.contracts.choices import ContractTypeChoices
from common.exceptions import PreconditionFailed

logger = logging.getLogger('django.server')


class OrderSerializer(serializers.ModelSerializer):
    order_item = serializers.CharField(source='order_item.id', help_text='주문 항목 ID')

    class Meta:
        model = Order
        fields = '__all__'
        ordering = ['-created_at']


class OrderCreateSerializer(serializers.ModelSerializer):
    mode = serializers.CharField(required=False, default=Order.MODES.new_order)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    status = serializers.HiddenField(default=Order.STATUS.processing)
    password = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = Order
        fields = ('order_item', 'status', 'mode', 'user', 'password')

    def validate(self, attrs):
        contract = attrs.get('order_item', None)
        logger.info('order request from : {user} - data: {data}'.format(user=self.context.get('request').user,
                                                                        data=attrs))

        if attrs.get('mode', None) == Order.MODES.new_order and contract.orders.exists():
            raise serializers.ValidationError({'mode': '{} mode already exist.'.format(attrs.get('mode'))})

        if contract \
                and contract.user == attrs.get('user') \
                and contract.vendor \
                and contract.status.code == get_contract_status(type='normal', code=True) \
                and contract.contract_type.is_orderable:
            attrs.update({
                'order_rep': contract.vendor
            })
        else:
            raise serializers.ValidationError({'order_item': 'invalid order_item.'})

        if contract.contract_type.operation_type == ContractTypeChoices.OPERATION_TYPE.D:
            # TODO Account->OMS 주문 이관 후 해당 분기문 제외처리
            risk_type = contract.risk_type
            universe = contract.contract_type.universe

            # 운용 포트폴리오 정보 확인
            portfolios = PortfolioDaily.objects.select_related('port_type') \
                .filter(port_type__universe_index__universe_index=universe, port_type__risk_type=risk_type)

            if not portfolios.exists():
                raise PreconditionFailed({'portfolio': 'portfolio does not exists.'})
            else:
                attrs.update({
                    'portfolio': portfolios.first()
                })

        return attrs

    def create(self, validated_data):
        contract = validated_data.get('order_item')
        account_alias = contract.account_alias

        if contract.contract_type.operation_type == ContractTypeChoices.OPERATION_TYPE.D:
            # TODO Account->OMS 주문 이관 후 해당 분기문 제외처리
            # 원장 서버의 관리계좌에 포트폴리오 정보 업데이트
            portfolio = validated_data.get('portfolio')
            del validated_data['portfolio']

            resp = account_adapter.request(f'api/v1/orders/', data={
                'account_alias': account_alias,
                'portfolio_id': portfolio.port_seq
            })
            if not resp:
                logger.error(f'account sync error. - account_alias: {account_alias}, user: {contract.user_id}')
        else:
            access_token = ea_oms_adapter.get_access_token(
                contract.user.profile.ci,
                contract.user.profile.birth_date,
                contract.user.profile.gender_code,
                contract.user.profile.name,
                contract.user.profile.phone,
            )
            resp = ea_oms_adapter.create_order(access_token, account_alias, validated_data.get('password'))
            if not resp:
                logger.error(f'fa oms sync error. - account_alias: {account_alias}, user: {contract.user_id}')

            if validated_data.get('password', None):
                del validated_data['password']

        instance = super().create(validated_data)
        return instance


class OrderBasketSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    universe_index = serializers.CharField(required=True, write_only=True)

    class Meta:
        model = Order
        fields = ('user', 'user', 'universe_index',)

    def to_representation(self, instance: Contract):
        access_token = ea_oms_adapter.get_access_token(
            instance.user.profile.ci,
            instance.user.profile.birth_date,
            instance.user.profile.gender_code,
            instance.user.profile.name,
            instance.user.profile.phone,
        )
        resp = ea_oms_adapter.get_order_basket(access_token, instance.account_alias)
        return resp


class OrderDetailSerializer(serializers.ModelSerializer):
    contract = serializers.UUIDField(source='account_alias.id', help_text="계약 ID")
    name = serializers.CharField(source='asset.name', help_text='종목명')

    class Meta:
        model = OrderDetail
        exclude = ['account_alias', ]
        ordering = ['-created_at']
