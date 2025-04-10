# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-03-20 07:35
from __future__ import unicode_literals

import common.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_auto_20190320_1316'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tendency',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL)),
                ('result', common.models.ListField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
