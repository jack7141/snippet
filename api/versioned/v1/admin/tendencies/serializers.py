from rest_framework import serializers

from api.bases.tendencies.models import Response


class ResponseAdminSerializer(serializers.ModelSerializer):
    user = serializers.UUIDField(read_only=True)
    name = serializers.CharField(source='user__profile__name', read_only=True)
    risk_type = serializers.IntegerField(source='user__profile__risk_type', read_only=True)

    class Meta:
        model = Response
        fields = ('user', 'name', 'risk_type', 'created_at')
