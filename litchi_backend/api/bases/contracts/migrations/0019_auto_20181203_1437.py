# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-12-03 05:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0018_auto_20181005_1408'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Condition',
            new_name='Term',
        ),
        migrations.RenameField(
            model_name='contract',
            old_name='condition',
            new_name='term',
        ),
        migrations.AlterField(
            model_name='contract',
            name='contract_type',
            field=models.CharField(choices=[('EA', 'ETF'), ('FA', '펀드'), ('PA', '연금')], help_text='계약 종류', max_length=2),
        ),
        migrations.AlterField(
            model_name='contract',
            name='rebalancing',
            field=models.BooleanField(default=False, help_text='리밸런싱 발생 여부'),
        ),
        migrations.AlterField(
            model_name='provisionalcontract',
            name='contract_type',
            field=models.CharField(choices=[('EA', 'ETF'), ('FA', '펀드'), ('PA', '연금')], help_text='임시 계약 종류', max_length=2),
        ),
    ]
