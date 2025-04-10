# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-05-15 04:56
from __future__ import unicode_literals

from django.db import migrations, models
from django.contrib.auth import get_user_model
from api.bases.authentications.models import Auth


def set_firm_agreement(apps, schema_editor):
    Contract = apps.get_model('contracts', 'contract')

    for user in get_user_model().objects.filter(profile__phone__isnull=False, is_active=True)\
            .only('profile', 'id'):
        auth_qs = Auth.objects.filter(etc_1=user.profile.phone, cert_type=3, is_verified=True).order_by('-created_date')

        if auth_qs.exists():
            auth = auth_qs.first()
            Contract.objects.filter(user_id=user.id, is_canceled=False).update(firm_agreement_at=auth.created_date)


class Migration(migrations.Migration):
    dependencies = [
        ('contracts', '0010_provisionalcontract_step'),
        ('users', '0005_auto_20180406_0605'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='firm_agreement_at',
            field=models.DateTimeField(blank=True, help_text='출금이체 동의 날짜', null=True),
        ),
        migrations.RunPython(
            set_firm_agreement,
            reverse_code=migrations.RunPython.noop
        )
    ]
