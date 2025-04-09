from django.contrib import admin, messages

from .models import (
    Type,
    ScoreRange,
    Question,
    Reason,
    Response,
    Answer,
)


class ScoreRangeInlineAdmin(admin.TabularInline):
    model = ScoreRange
    extra = 0
    ordering = ('risk_type',)


class QuestionInlineAdmin(admin.TabularInline):
    model = Question
    extra = 0
    ordering = ('order',)


class AnswerInlineAdmin(admin.TabularInline):
    model = Answer
    extra = 0
    ordering = ('question__order',)
    readonly_fields = ('question', 'answer', 'score',)
    can_delete = False


@admin.register(Type)
class TypeAdmin(admin.ModelAdmin):
    inlines = (ScoreRangeInlineAdmin, QuestionInlineAdmin,)
    list_display = ('code', 'name', 'is_published', 'exp_days', 'created_at', 'updated_at',)

    def save_model(self, request, obj, form, change):
        try:
            obj.save()
        except Exception as e:
            messages.error(request, e)


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    inlines = (AnswerInlineAdmin,)
    list_display = ('type', 'user', 'total_score', 'risk_type', 'created_at', 'updated_at')
    list_filter = ('type',)
    ordering = ('-created_at',)

    readonly_fields = ('type', 'user', 'total_score', 'risk_type', 'created_at')


@admin.register(Reason)
class ReasonAdmin(admin.ModelAdmin):
    list_display = ('order', 'title', 'text', 'is_publish', 'created_at', 'updated_at')
    ordering = ('-order',)
