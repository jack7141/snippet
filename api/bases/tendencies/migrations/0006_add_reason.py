# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2022-11-04 06:14
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import model_utils.fields
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('tendencies', '0005_response_sign'),
    ]

    operations = [
        migrations.CreateModel(
            name='Reason',
            fields=[
                ('id',
                 models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='생성일')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='수정일')),
                ('order', models.PositiveIntegerField(default=0, help_text='표시 순서')),
                ('title', models.TextField(help_text='재분석 타이틀')),
                ('text', models.TextField(help_text='재분석 사유')),
                ('is_publish', models.BooleanField(default=False, help_text='재분석 사유 발행 여부'))
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='response',
            name='reason',
            field=models.ForeignKey(help_text='재분석 사유', null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='reason', to='tendencies.Reason'),
        ),
    ]
