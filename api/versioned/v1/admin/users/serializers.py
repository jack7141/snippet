from rest_framework import serializers
from api.bases.users.models import User, ExpiringToken, Profile


class UserTokenSerializer(serializers.ModelSerializer):
    token = serializers.CharField(source='key')

    class Meta:
        model = ExpiringToken
        fields = ('token',)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('email',)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        exclude = ('user', 'config',)


class UserSimpleSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ('id', 'email', 'profile', 'is_active', 'is_staff', 'date_joined')


class UserIssuanceSeriaizer(UserSerializer):
    name = serializers.CharField(source='profile.name')
    birth_date = serializers.DateField(source='profile.birth_date')
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ('id', 'email', 'name', 'birth_date', 'profile')
