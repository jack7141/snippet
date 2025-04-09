# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2022-04-23 20:41
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import model_utils.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Answer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='생성일')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='수정일')),
                ('answer', models.CharField(help_text='응답 결과', max_length=512)),
                ('score', models.IntegerField(blank=True, help_text='응답 결과 점수', null=True)),
            ],
            options={
                'ordering': ('question__order',),
            },
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='생성일')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='수정일')),
                ('order', models.PositiveIntegerField(default=0, help_text='표시 순서')),
                ('question_type', model_utils.fields.StatusField(choices=[('select', 'select'), ('multiple_select', 'multiple_select')], default='select', help_text='답변 유형', max_length=100, no_check_for_status=True)),
                ('title', models.TextField(help_text='질문 타이틀')),
                ('text', models.TextField(help_text='질문지')),
                ('separator_type', model_utils.fields.StatusField(choices=[(',', '쉼표'), ('.', '마침표'), ('|', '분리선'), (':', '쌍점')], default=',', help_text='분리 기호(,=쉼표 .=마침표 |=분리선 :=쌍점', max_length=100, no_check_for_status=True)),
                ('choices', models.TextField(help_text='답변안')),
                ('scores', models.TextField(help_text='배점안')),
            ],
            options={
                'ordering': ('order', 'created_at'),
            },
        ),
        migrations.CreateModel(
            name='Response',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='생성일')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='수정일')),
                ('total_score', models.IntegerField(blank=True, help_text='응답값 총점', null=True)),
                ('risk_type', models.IntegerField(blank=True, help_text='투자위험(위험성향)', null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ScoreRange',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='생성일')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='수정일')),
                ('risk_type', model_utils.fields.StatusField(choices=[('0', '안정형'), ('1', '안정추구형'), ('2', '중립형'), ('3', '성장형'), ('4', '공격형')], default='0', help_text='투자위험(위험성향) 분류', max_length=100, no_check_for_status=True)),
                ('start', models.PositiveIntegerField(default=0, help_text='범위 시작값')),
                ('end', models.PositiveIntegerField(default=0, help_text='범위 종료값')),
            ],
        ),
        migrations.CreateModel(
            name='Type',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='생성일')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='수정일')),
                ('code', models.CharField(help_text='투자성향 분석 코드', max_length=60)),
                ('name', models.CharField(help_text='투자성향 분석 한글명', max_length=60)),
                ('description', models.TextField(help_text='설문지 설명')),
                ('exp_days', models.PositiveIntegerField(default=365, help_text='투자성향 분석 유효기간')),
                ('is_published', models.BooleanField(default=False, help_text='배포여부')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='scorerange',
            name='type',
            field=models.ForeignKey(help_text='투자성향 분석 타입', on_delete=django.db.models.deletion.CASCADE, related_name='score_ranges', to='tendencies.Type'),
        ),
        migrations.AddField(
            model_name='response',
            name='type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='responses', to='tendencies.Type'),
        ),
        migrations.AddField(
            model_name='response',
            name='user',
            field=models.ForeignKey(help_text='유저', on_delete=django.db.models.deletion.CASCADE, related_name='tendency_responses', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='question',
            name='type',
            field=models.ForeignKey(help_text='투자성향 분석 타입', on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='tendencies.Type'),
        ),
        migrations.AddField(
            model_name='answer',
            name='question',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='tendencies.Question'),
        ),
        migrations.AddField(
            model_name='answer',
            name='response',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='tendencies.Response'),
        ),
        migrations.AlterUniqueTogether(
            name='scorerange',
            unique_together=set([('type', 'risk_type')]),
        ),
        migrations.AlterUniqueTogether(
            name='answer',
            unique_together=set([('question', 'response')]),
        ),
    ]
