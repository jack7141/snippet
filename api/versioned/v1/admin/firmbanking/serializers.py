from rest_framework import serializers
from api.bases.authentications.models import Auth
from api.bases.contracts.models import Contract
from rest_framework import status

from django.contrib.auth import get_user_model


class AuthenticationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auth
        fields = ('id', 'user', 'cert_type', 'is_verified', 'is_expired', 'etc_3',)
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }


class AuthAccountSerializer(serializers.ModelSerializer):
    bank_code_std = serializers.CharField(source='etc_encrypted_2', help_text="은행표준코드")
    account_number = serializers.CharField(source='etc_encrypted_3', help_text="계좌번호")

    class Meta:
        model = Auth
        fields = ['bank_code_std', 'account_number']
        error_status_codes = {
            status.HTTP_404_NOT_FOUND: None,
        }
