from rest_framework import serializers

from api.bases.agreements.models import Type, Agreement, AgreementGroup


class TypeSerializer(serializers.ModelSerializer):
    title = serializers.SlugRelatedField(source='agreement_group', slug_field='title',
                                         queryset=AgreementGroup.objects.all(), help_text='동의 타입 그룹')
    latest_agreed_at = serializers.SerializerMethodField(read_only=True, help_text='마지막 동의 일시')

    class Meta:
        model = Type
        fields = ('id', 'title', 'code', 'name', 'description', 'is_required', 'exp_days', 'agreement_file', 'latest_agreed_at')

    def latest_created_at(self, instance):
        try:
            agreed = instance.agreement.filter(user=self.context.get('request').user).latest('created_at')
            return agreed.created_at
        except:
            return None

    def get_latest_agreed_at(self, instance):
        return serializers.DateTimeField().to_representation(self.latest_created_at(instance))


class AgreementGroupSerializer(serializers.ModelSerializer):
    type = TypeSerializer(many=True, source='types')

    class Meta:
        model = AgreementGroup
        fields = ('id', 'title', 'is_default', 'is_publish', 'type', 'created_at', 'updated_at')


class AgreementSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    title = serializers.SlugRelatedField(source='agreement_group', slug_field='title',
                                         queryset=AgreementGroup.objects.all(), help_text='동의 타입 그룹')
    code = serializers.SlugRelatedField(source='type', slug_field='code', queryset=Type.objects.all(),
                                        help_text='동의 타입 코드')
    name = serializers.SlugRelatedField(source='type', slug_field='name', read_only=True, help_text='동의 명')
    is_required = serializers.SlugRelatedField(source='type', slug_field='is_required', read_only=True,
                                               help_text='필수 동의 여부')

    class Meta:
        model = Agreement
        fields = ('id', 'user', 'title', 'code', 'name', 'is_required', 'created_at',)
