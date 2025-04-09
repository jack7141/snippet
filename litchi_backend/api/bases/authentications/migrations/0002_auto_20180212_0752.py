# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-02-12 07:52
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import fernet_fields.fields
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentications', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Integrate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('ci', fernet_fields.fields.EncryptedCharField(max_length=88)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='CI 적용 일시')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ci_from', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='integrates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-user', '-updated_at'),
            },
        ),
        migrations.AlterModelOptions(
            name='auth',
            options={'ordering': ('-created_date',)},
        ),
        migrations.AlterField(
            model_name='auth',
            name='cert_type',
            field=models.CharField(choices=[('1', 'sms'), ('2', 'accounts')], max_length=1),
        ),
        migrations.AlterField(
            model_name='auth',
            name='code',
            field=models.CharField(help_text='인증코드', max_length=6),
        ),
        migrations.AlterField(
            model_name='auth',
            name='created_date',
            field=models.DateTimeField(auto_now_add=True, help_text='인증요청 일시'),
        ),
        migrations.AlterField(
            model_name='auth',
            name='is_expired',
            field=models.BooleanField(default=False, help_text='만료여부'),
        ),
        migrations.AlterField(
            model_name='auth',
            name='is_verified',
            field=models.BooleanField(default=False, help_text='인증여부'),
        ),
    ]
