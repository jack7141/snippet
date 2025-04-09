from collections import OrderedDict

from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.fields import SkipField
from rest_framework.relations import PKOnlyObject

from api.bases.authentications.models import Auth
from api.bases.contracts.models import Contract

from common.exceptions import PreconditionRequired


class CertValidRespSerializer(serializers.ModelSerializer):
    code = serializers.CharField(allow_null=False, allow_blank=False,
                                 required=True, write_only=True,
                                 help_text='인증코드')

    class Meta:
        model = Auth
        fields = ['code']
        success_status_code = 200
        error_status_codes = {
            status.HTTP_401_UNAUTHORIZED: "인증 실패"
        }


class SMSCertSerializer(serializers.ModelSerializer):
    phone = serializers.RegexField('^01([0|1|6|7|8|9]?)?([0-9]{3,4})?([0-9]{4})$',
                                   allow_blank=False, allow_null=False, required=True, source='etc_1',
                                   help_text='휴대폰 번호)')
    user = serializers.CharField(source='user.email', read_only=True, help_text="유저 계정명")

    class Meta:
        model = Auth
        fields = ['phone', 'code', 'is_verified', 'is_expired', 'created_date', 'user']


class SMSCertCreateSerializer(SMSCertSerializer):
    class Meta:
        model = Auth
        fields = ['phone']
        error_status_codes = {
            status.HTTP_400_BAD_REQUEST: None,
            status.HTTP_429_TOO_MANY_REQUESTS: None
        }


class AccountCertSerializer(serializers.ModelSerializer):
    bank_code_std = serializers.CharField(max_length=3, min_length=3, required=True, initial='278',
                                          source='etc_1', help_text="은행표준코드")
    account_number = serializers.CharField(allow_null=False, allow_blank=False, max_length=24, min_length=10,
                                           required=True, source='etc_encrypted_1', help_text="계좌번호")
    account_holder_name = serializers.CharField(allow_null=False, allow_blank=False,
                                                required=True, source='etc_encrypted_2', help_text="계좌주명")

    class Meta:
        model = Auth
        fields = ['account_number', 'account_holder_name', 'bank_code_std',
                  'code', 'is_verified', 'is_expired', 'created_date', 'user']


class AccountCertCreateSerializer(AccountCertSerializer):
    class Meta:
        model = Auth
        fields = ['account_number', 'account_holder_name', 'bank_code_std']
        error_status_codes = {
            status.HTTP_400_BAD_REQUEST: None,
            status.HTTP_412_PRECONDITION_FAILED: None,
            status.HTTP_428_PRECONDITION_REQUIRED: None,
            status.HTTP_429_TOO_MANY_REQUESTS: None
        }

    def is_valid(self, raise_exception=False):
        if super(AccountCertCreateSerializer, self).is_valid(raise_exception=raise_exception):
            user = self.context.get('request').user
            username = user.profile.name
            name_field = 'account_holder_name'

            if not username and raise_exception:
                raise PreconditionRequired(
                    {name_field: "there is no user name. please set name in user's profile before use this API."})

            if username != self.validated_data.get('etc_encrypted_2'):
                if raise_exception:
                    raise serializers.ValidationError(
                        {name_field: "user name dose not matched."})
                else:
                    return False
            return True
        else:
            return False


class AccountRealNameSerializer(serializers.Serializer):
    bank_code_std = serializers.CharField(max_length=3, min_length=3, required=True, initial='278', write_only=True,
                                          help_text="은행표준코드")
    account_number = serializers.CharField(max_length=24, min_length=10, required=True, source='account_num',
                                           write_only=True, help_text="계좌번호")
    account_holder_info = serializers.CharField(max_length=7, min_length=6, required=True, write_only=True,
                                                help_text="예금주 인증정보")

    class Meta:
        success_status_code = 200
        error_status_codes = {
            status.HTTP_400_BAD_REQUEST: None,
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_412_PRECONDITION_FAILED: None,
            status.HTTP_428_PRECONDITION_REQUIRED: None
        }

    def is_valid(self, raise_exception=False):
        if super(AccountRealNameSerializer, self).is_valid(raise_exception=raise_exception):
            user = self.context.get('request').user
            username = user.profile.name

            if not username and raise_exception:
                raise PreconditionRequired(
                    {'user': "there is no user name. please set name in user's profile before use this API."})
            else:
                return False
            return True
        else:
            return False

    def to_representation(self, instance):
        ret = OrderedDict()
        fields = self._writable_fields

        for field in fields:
            try:
                attribute = field.get_attribute(instance)
            except SkipField:
                continue

            check_for_none = attribute.pk if isinstance(attribute, PKOnlyObject) else attribute
            if check_for_none is None:
                ret[field.field_name] = None
            else:
                field_name = field.source if field.source else field.field_name
                ret[field_name] = field.to_representation(attribute)

        ret['tran_dtime'] = timezone.now().strftime("%Y%m%d%H%M%S")

        return ret


class ARSCertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auth


class ARSCertCreateSerializer(ARSCertSerializer):
    contract_id = serializers.UUIDField(source='etc_2', help_text='계약 id')
    security = serializers.CharField(source='code', help_text='인증번호')

    class Meta:
        model = Auth
        fields = ['id', 'contract_id', 'security']
        extra_kwargs = {
            'id': {'read_only': True}
        }
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
            status.HTTP_412_PRECONDITION_FAILED: None,
            status.HTTP_429_TOO_MANY_REQUESTS: None
        }

    def validate(self, attrs):
        contract_id = attrs.get('etc_2')

        try:
            contract = Contract.objects.filter(user=self.context.get('request').user, is_canceled=False).get(
                id=contract_id)
        except Contract.DoesNotExist:
            raise NotFound()

        # Vendor 정보가 없거나, 정상 정상 계좌개설 되지않은 계약인 경우는 조건실패 처리
        if not contract.vendor.vendor_props or \
                (contract.account_number == contract.account_alias == contract.contract_number):
            raise PreconditionRequired(detail='vendor must be defined' % contract)

        attrs['etc_1'] = self.context.get('request').user.profile.phone
        attrs['user_id'] = self.context.get('request').user.id
        return attrs


class OwnerCreateSerializer(serializers.ModelSerializer):
    contract_id = serializers.UUIDField(source='etc_2', help_text='계약 id')
    bank_code_std = serializers.CharField(max_length=3, min_length=3, required=True, initial='278', source='etc_1',
                                          help_text="은행표준코드")
    account_number = serializers.CharField(allow_null=False, allow_blank=False, max_length=24, min_length=10,
                                           required=True, source='etc_encrypted_1', help_text="계좌번호")

    class Meta:
        model = Auth
        fields = ['id', 'contract_id', 'bank_code_std', 'account_number']

    def validate(self, attrs):
        contract_id = attrs.get('etc_2')
        try:
            contract = Contract.objects.filter(user=self.context.get('request').user, is_canceled=False).get(
                id=contract_id)
        except Contract.DoesNotExist:
            raise NotFound()

        # Vendor 정보가 없거나, 정상 계좌개설 되지않은 계약인 경우는 조건실패 처리
        if not contract.vendor.vendor_props or \
                (contract.account_number == contract.account_alias == contract.contract_number):
            raise PreconditionRequired(detail='None vendor or abnormal account. contract: %s' % contract)

        attrs['user_id'] = self.context.get('request').user.id
        return attrs


class AuthAccountSerializer(serializers.ModelSerializer):
    contract_id = serializers.UUIDField(source='etc_2', help_text='계약 id')
    bank_code_std = serializers.CharField(source='etc_encrypted_2', help_text="은행표준코드")
    account_number = serializers.CharField(source='etc_encrypted_3', help_text="계좌번호")

    class Meta:
        model = Auth
        fields = ['contract_id', 'bank_code_std', 'account_number']
