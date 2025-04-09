import logging
from django.contrib.auth import get_user_model

from rest_framework import serializers, exceptions

from api.bases.tendencies.models import Type, Question, Response, Answer, ScoreRange, Reason
from api.bases.users.models import Profile

from api.versioned.v1.tendencies.mixins import RiskTypeMixin

logger = logging.getLogger('django.server')


class ProfileSerializer(serializers.ModelSerializer):
    personal_type = serializers.IntegerField()

    class Meta:
        model = Profile
        fields = ('personal_type',)


class UserProfileSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=True)

    class Meta:
        model = get_user_model()
        fields = ('profile',)


class TypeSerializer(serializers.ModelSerializer):
    class _QuestionSerializer(serializers.ModelSerializer):
        class Meta:
            model = Question
            fields = ('order', 'question_type', 'title', 'text', 'separator_type', 'choices', 'scores')
            ordering = ['order']

    class _ScoreRangeSerializer(serializers.ModelSerializer):
        class Meta:
            model = ScoreRange
            fields = ('risk_type', 'start', 'end')

    questions = _QuestionSerializer(many=True)
    score_ranges = _ScoreRangeSerializer(many=True)

    class Meta:
        model = Type
        fields = ('id', 'code', 'name', 'description', 'exp_days', 'questions', 'score_ranges', 'is_default')
        ordering = ['-created_at']


class ReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reason
        fields = '__all__'


class ResponseSerializer(serializers.ModelSerializer):
    class _AnswerSerializer(serializers.ModelSerializer):
        order = serializers.IntegerField(source='question.order', read_only=True, help_text='순번')
        question = serializers.CharField(source='question.text', read_only=True, help_text='질문 내용')

        class Meta:
            model = Answer
            fields = ('order', 'question', 'answer',)

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    type = TypeSerializer(read_only=True)
    answers = _AnswerSerializer(many=True)
    total_score = serializers.IntegerField(read_only=True)
    risk_type = serializers.IntegerField(read_only=True)

    class Meta:
        model = Response
        fields = '__all__'


class ResponseCreateSerializer(serializers.ModelSerializer, RiskTypeMixin):
    user = UserProfileSerializer(required=False)
    code = serializers.SlugRelatedField(slug_field='code',
                                        queryset=Type.objects.filter(is_published=True),
                                        source='type')
    answers = serializers.ListField(required=True, write_only=True)
    total_score = serializers.IntegerField(read_only=True)
    risk_type = serializers.IntegerField(read_only=True)
    reason = serializers.SlugRelatedField(slug_field='order',
                                          required=False,
                                          queryset=Reason.objects.all())

    class Meta:
        model = Response
        fields = ('user', 'code', 'answers', 'total_score', 'risk_type', 'auth_type', 'sign', 'reason')
        extra_kwargs = {
            'sign': {'write_only': True},
        }

    def is_valid(self, raise_exception=False):
        if super().is_valid(raise_exception=raise_exception):
            user = self.validated_data.get('user')
            type = self.validated_data.get('type')
            answers = self.validated_data.get('answers')

            questions = type.questions.all().order_by('order')

            # 질문 갯수와 응답 갯수가 같은지
            if len(answers) != questions.count():
                raise exceptions.ValidationError(detail={
                    'invalid_answers': 'miss match answer count'
                })

            errors = []
            for item in questions:
                if not item.check_answer(answers[item.order], answer_type='index'):
                    errors.append({
                        'answer_no': int(item.order),
                        'question': item.text,
                        'available_choices': item.choices,
                        'answer': answers[item.order]
                    })

            if errors and raise_exception:
                raise exceptions.ValidationError(detail={
                    'invalid_answers': errors
                })

        return False

    def create(self, validated_data):
        answers = validated_data.get('answers')
        type = validated_data.get('type')
        user = validated_data.get('user')

        if answers:
            del validated_data['answers']

        if user:
            del validated_data['user']

        validated_data['user'] = self.context['request'].user
        instance = super().create(validated_data)

        try:
            if answers:
                questions = type.questions.all().order_by('order')
                Answer.objects.bulk_create(
                    [Answer(
                        question=question,
                        answer=question.get_answer(answers[question.order], answer_type='index'),
                        score=question.get_score(answers[question.order], answer_type='index'),
                        response=instance) for question in
                        questions
                    ])
                instance.update_score()
        except Exception as e:
            instance.delete()
            raise exceptions.ValidationError(detail=e)

        try:
            if user:
                instance.user.profile.personal_type = user['profile']['personal_type']
                instance.user.profile.save(update_fields=['personal_type'])
        except Exception as e:
            raise exceptions.ValidationError(detail=e)

        try:
            self.process_advisory(instance)
            self.process_discretionary(instance)
        except Exception as e:
            raise exceptions.NotAcceptable(detail=e)

        return instance
