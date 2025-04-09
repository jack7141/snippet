# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-12-11 02:16
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0006_migrate_subscribe_news_topic'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscribe',
            name='type',
            field=models.CharField(choices=[('1', 'SMS'), ('2', 'EMAIL'), ('3', 'PUSH'), ('4', 'APP')], help_text='protocol 종류', max_length=1),
        ),
    ]
