# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-04-11 10:16
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contracts', '0007_auto_20180406_1255'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProvisionalContract',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, help_text='임시 계약 UUID', primary_key=True, serialize=False, unique=True)),
                ('account_number', models.CharField(help_text='임시계좌번호', max_length=128, unique=True)),
                ('contract_type', models.CharField(choices=[('EA', 'ETF Advisor'), ('FA', 'FUND Advisor')], help_text='임시 계약 종류', max_length=2)),
                ('is_contract', models.BooleanField(default=False, help_text='계약 생성 여부')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='임시 계약 체결일')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='수정일')),
                ('user', models.ForeignKey(help_text='계약자', on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'contracts_provisional',
            },
        ),
    ]
