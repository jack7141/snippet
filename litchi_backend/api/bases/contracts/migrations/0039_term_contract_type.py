# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2022-06-19 15:39
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('contracts', '0038_contract_acct_completed_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='term',
            name='contract_type',
            field=models.ForeignKey(blank=True, db_column='contract_type', help_text='계약종류', null=True,
                                    on_delete=django.db.models.deletion.PROTECT, related_name='term',
                                    to='contracts.ContractType'),
        ),
    ]
