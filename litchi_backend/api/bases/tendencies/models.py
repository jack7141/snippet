from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.template.defaultfilters import truncatechars

from fernet_fields import EncryptedTextField

from model_utils.fields import StatusField

from common.behaviors import UniqueTimestampable
from common.decorators import cached_property

from api.bases.tendencies.choices import ScoreRangeChoices, QuestionChoices, ResponseChoices

DEFAULT_TYPE_CODE = 'fount'


class Type(UniqueTimestampable):
    code = models.CharField(max_length=60, blank=False, null=False, help_text='투자성향 분석 코드')
    name = models.CharField(max_length=60, blank=False, null=False, help_text='투자성향 분석 한글명')
    description = models.TextField(help_text='설문지 설명')
    exp_days = models.PositiveIntegerField(default=365, blank=False, null=False, help_text='투자성향 분석 유효기간')
    is_published = models.BooleanField(default=False, help_text='배포여부')

    def __str__(self):
        return f'{self.code} | {self.name}{"(*)" if self.is_published else ""}'

    @cached_property
    def is_default(self):
        return bool(self.code == DEFAULT_TYPE_CODE and self.is_published)

    def save(self, *args, **kwargs):
        if self.is_published:
            try:
                temp = Type.objects.get(code=self.code, is_published=True)
                if self != temp:
                    temp.is_published = False
                    temp.save()
            except Type.DoesNotExist:
                pass
        super(Type, self).save(*args, **kwargs)


class ScoreRange(UniqueTimestampable):
    RISK_TYPES = ScoreRangeChoices.RISK_TYPES

    type = models.ForeignKey(Type, on_delete=models.CASCADE, related_name='score_ranges', help_text='투자성향 분석 타입')
    risk_type = StatusField(choices_name='RISK_TYPES', default=RISK_TYPES.lowest, help_text='투자위험(위험성향) 분류')
    start = models.IntegerField(default=0, help_text='범위 시작값')
    end = models.IntegerField(default=0, help_text='범위 종료값')

    class Meta:
        unique_together = (('type', 'risk_type'),)


class Question(UniqueTimestampable):
    QUESTION_TYPES = QuestionChoices.QUESTION_TYPES
    SEPARATOR_TYPES = QuestionChoices.SEPARATOR_TYPES

    type = models.ForeignKey(Type, on_delete=models.CASCADE, related_name='questions', help_text='투자성향 분석 타입')
    order = models.PositiveIntegerField(default=0, help_text='표시 순서')
    question_type = StatusField(choices_name='QUESTION_TYPES', default=QUESTION_TYPES.select, help_text='답변 유형')
    title = models.TextField(help_text='질문 타이틀')
    text = models.TextField(help_text='질문지')
    separator_type = StatusField(choices_name='SEPARATOR_TYPES', default=SEPARATOR_TYPES.comma,
                                 help_text='분리 기호(,=쉼표 .=마침표 |=분리선 :=쌍점')
    choices = models.TextField(blank=False, null=False, help_text='답변안')
    scores = models.TextField(blank=False, null=False, help_text='배점안')

    def __str__(self):
        return f'{truncatechars(self.text, 32)}'

    class Meta:
        ordering = ('order', 'created_at')

    def get_clean_choices(self, answer_type='str'):
        if self.choices is None:
            return []
        choices_list = []
        for index, choice in enumerate(self.choices.split(self.separator_type)):
            choice = choice.strip()
            if choice:
                choices_list.append(choice if answer_type == 'str' else str(index))
        return choices_list

    def populate_answer(self, answer_type='str'):
        str_choices = self.get_clean_choices('str')
        index_choices = self.get_clean_choices('index')

        if answer_type == 'str':
            return dict(zip(str_choices, index_choices))
        else:
            return dict(zip(index_choices, str_choices))

    def get_answer(self, answer, answer_type='str'):
        populate_answer = self.populate_answer(answer_type)
        answers = []

        if self.question_type == QuestionChoices.QUESTION_TYPES.multiple_select:
            selected = str(answer).split(self.separator_type)

            for item in selected:
                answers.append(populate_answer.get(str(item)))
        else:
            answers.append(populate_answer.get(str(answer)))

        return self.separator_type.join(answers)

    def check_answer(self, answer, answer_type='str'):
        selected = str(answer).split(self.separator_type)

        # select 타입인 경우는 1개만 선택 강제화
        if self.question_type == QuestionChoices.QUESTION_TYPES.select and len(selected) > 1:
            return False
        _set = set(self.populate_answer(answer_type))

        # 선택된 값이 choice에 설정된 값 내에 있는지 검사
        return bool(_set.issuperset(selected))

    def populate_score(self, answer_type='str'):
        return dict(zip(self.get_clean_choices(answer_type), self.scores.split(self.separator_type)))

    def get_score(self, answer, answer_type='str'):
        populated_score = self.populate_score(answer_type)
        scores = []

        if self.question_type == QuestionChoices.QUESTION_TYPES.multiple_select:
            selected = str(answer).split(self.separator_type)

            for item in selected:
                scores.append(populated_score.get(item))
        else:
            scores.append(populated_score.get(str(answer)))

        return max(scores)


class Reason(UniqueTimestampable):
    order = models.PositiveIntegerField(default=0, help_text='표시 순서')
    title = models.TextField(help_text='재분석 타이틀')
    text = models.TextField(help_text='재분석 사유')
    is_publish = models.BooleanField(default=False, help_text='재분석 사유 발행 여부')


class Response(UniqueTimestampable):
    AUTH_TYPES = ResponseChoices.AUTH_TYPES

    type = models.ForeignKey(Type, on_delete=models.PROTECT, related_name='responses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tendency_responses',
                             help_text='유저')
    total_score = models.IntegerField(null=True, blank=True, help_text='응답값 총점')
    risk_type = models.IntegerField(null=True, blank=True, help_text='투자위험(위험성향)')
    auth_type = StatusField(choices_name='AUTH_TYPES', default=AUTH_TYPES.password, null=True, blank=True,
                            help_text='투자성향 인증수단')
    reason = models.ForeignKey(Reason, on_delete=models.SET_NULL, related_name='reason', null=True,
                               help_text='재분석 사유')
    sign = EncryptedTextField(blank=True, null=True, help_text='서명 정보 Base64')

    class Meta:
        ordering = ('-created_at',)

    def save(self, *args, **kwargs):
        self.total_score = self.get_total_score()
        super().save(*args, **kwargs)

    def get_total_score(self):
        return sum(list(self.answers.all().values_list('score', flat=True)))

    def get_risk_type(self):
        score_ranges = self.type.score_ranges.all().values('start', 'end', 'risk_type').order_by('risk_type')
        score = self.total_score or self.get_total_score()

        for score_range in score_ranges:
            start = score_range.get('start')
            end = score_range.get('end')

            if start <= score <= end:
                return score_range.get('risk_type')

        return None

    def update_score(self):
        self.total_score = self.get_total_score()
        self.risk_type = self.get_risk_type()
        self.save(update_fields=['total_score', 'risk_type'])


class Answer(UniqueTimestampable):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name='answers')
    answer = models.CharField(max_length=512, null=False, blank=False, help_text='응답 결과')
    score = models.IntegerField(null=True, blank=True, help_text='응답 결과 점수')

    class Meta:
        unique_together = (('question', 'response'),)
        ordering = ('question__order',)

    def save(self, *args, **kwargs):
        if not self.question.check_answer(self.answer):
            raise ValidationError({'answer': 'invalid answer'})
        self.score = self.question.populate_answer().get(self.answer)

        super().save(*args, **kwargs)
