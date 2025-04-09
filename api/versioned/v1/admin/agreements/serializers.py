from rest_framework import serializers

from api.bases.agreements.models import Type, Agreement


class TypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Type
        fields = '__all__'


class AgreementSerializer(serializers.ModelSerializer):
    email = serializers.SlugRelatedField(source='user', slug_field='email', read_only=True)
    code = serializers.SlugRelatedField(source='type', slug_field='code', read_only=True)
    name = serializers.SlugRelatedField(source='type', slug_field='name', read_only=True)
    is_required = serializers.SlugRelatedField(source='type', slug_field='is_required', read_only=True)

    class Meta:
        model = Agreement
        fields = '__all__'
