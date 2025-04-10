# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-12-07 02:59
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import fernet_fields.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Auth',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('cert_type', models.CharField(choices=[('1', 'sms'), ('2', 'account')], max_length=1)),
                ('code', models.CharField(max_length=6)),
                ('is_verified', models.BooleanField(default=False)),
                ('is_expired', models.BooleanField(default=False)),
                ('etc_1', models.CharField(blank=True, max_length=128, null=True)),
                ('etc_2', models.CharField(blank=True, max_length=128, null=True)),
                ('etc_3', models.CharField(blank=True, max_length=128, null=True)),
                ('etc_encrypted_1', fernet_fields.fields.EncryptedCharField(blank=True, max_length=128, null=True)),
                ('etc_encrypted_2', fernet_fields.fields.EncryptedCharField(blank=True, max_length=128, null=True)),
                ('etc_encrypted_3', fernet_fields.fields.EncryptedCharField(blank=True, max_length=128, null=True)),
                ('created_date', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
