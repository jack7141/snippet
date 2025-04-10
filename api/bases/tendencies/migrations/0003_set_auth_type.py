# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2022-06-22 03:16
from __future__ import unicode_literals

from django.db import migrations


def set_auth_type(apps, schema_editor):
    Response = apps.get_model('tendencies', 'response')
    Response.objects.update(auth_type='30')


class Migration(migrations.Migration):
    dependencies = [
        ('tendencies', '0002_response_auth_type'),
    ]

    operations = [
        migrations.RunPython(
            set_auth_type,
            reverse_code=migrations.RunPython.noop
        ),
    ]
