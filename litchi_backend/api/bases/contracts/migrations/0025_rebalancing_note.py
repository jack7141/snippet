# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2019-01-02 07:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0024_rebalancing'),
    ]

    operations = [
        migrations.AddField(
            model_name='rebalancing',
            name='note',
            field=models.CharField(blank=True, help_text='기타 사항', max_length=128, null=True),
        ),
    ]
