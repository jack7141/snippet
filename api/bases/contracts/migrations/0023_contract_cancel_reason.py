# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-12-26 13:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0022_auto_20181224_1449'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='cancel_reason',
            field=models.CharField(blank=True, help_text='계약 취소 사유', max_length=128, null=True),
        ),
    ]
