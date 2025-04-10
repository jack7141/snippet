# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2023-01-02 07:01
from __future__ import unicode_literals

from django.db import migrations, models


def migrate_transfer_canceled_at(apps, schema_editor):
    Transfer = apps.get_model('contracts', 'transfer')

    for item in Transfer.objects.all():
        if item.is_canceled:
            Transfer.objects.filter(id=item.pk).update(canceled_at=item.updated_at)


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0052_contracttype_fixed_risk_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='transfer',
            name='canceled_at',
            field=models.DateTimeField(blank=True, editable=False, help_text='해지일', null=True),
        ),
        migrations.RunPython(
            migrate_transfer_canceled_at,
            reverse_code=migrations.RunPython.noop
        ),
    ]
