# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2022-09-19 12:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0040_add_transfer'),
    ]

    operations = [
        migrations.AddField(
            model_name='transfer',
            name='is_canceled',
            field=models.BooleanField(default=False, help_text='계약 이전 취소'),
        ),
        migrations.AlterField(
            model_name='transfer',
            name='status',
            field=models.IntegerField(choices=[(0, '해지됨'), ('Pension', [(10, '이체신청'), (11, '가입확인'), (12, '이체예정'), (13, '이체접수'), (14, '이체납입명세'), (15, '이체실패'), (16, '자동취소')])], default=10, help_text='이전 상태'),
        ),
    ]
