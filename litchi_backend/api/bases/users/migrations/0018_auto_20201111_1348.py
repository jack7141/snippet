# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2020-11-11 04:48
from __future__ import unicode_literals

import api.bases.users.models
from django.db import migrations, models


def set_referral_code(apps, schema_editor):
    User = apps.get_model('users', 'user')

    for user in User.objects.iterator():
        user.referral_code = api.bases.users.models.generate_referral_code()
        user.save()


class Migration(migrations.Migration):
    dependencies = [
        ('sites', '0002_alter_domain_unique'),
        ('users', '0017_vendorproperty_terminate_msg'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='referral_code',
            field=models.CharField(default='', editable=False, help_text='추천인 코드', max_length=10),
        ),
        migrations.RunPython(
            set_referral_code,
            reverse_code=migrations.RunPython.noop
        ),
        migrations.AlterUniqueTogether(
            name='user',
            unique_together=set([('email', 'site', 'referral_code')]),
        ),
    ]
