# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2022-06-16 01:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0022_profile_avatar'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='nickname',
            field=models.CharField(blank=True, help_text='별명', max_length=30, null=True),
        ),
    ]
