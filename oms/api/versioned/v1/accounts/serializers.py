from api.bases.accounts.models import Account, AssetDetail
from rest_framework import serializers


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = "__all__"


class AssetDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetDetail
        fields = "__all__"
