# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2022-06-28 11:09
from __future__ import unicode_literals

from django.db import migrations
import fernet_fields.fields


class Migration(migrations.Migration):

    dependencies = [
        ('tendencies', '0004_auto_20220625_1028'),
    ]

    operations = [
        migrations.AddField(
            model_name='response',
            name='sign',
            field=fernet_fields.fields.EncryptedTextField(blank=True, help_text='서명 정보 Base64', null=True),
        ),
    ]
