# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2020-11-03 01:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0016_auto_20200918_1330'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendorproperty',
            name='terminate_msg',
            field=models.CharField(default='', help_text='해지용 메시지', max_length=128),
            preserve_default=False,
        ),
    ]
