# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-10-05 05:08
from __future__ import unicode_literals

from django.db import migrations


def set_rebalancing(apps, schema_editor):
    Order = apps.get_model('orders', 'order')

    for order in Order.objects.filter(mode='rebalancing', status=3):
        order.order_item.rebalancing = True
        order.order_item.save()
        order.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('contracts', '0017_contract_force_rebalancing'),
        ('orders', '0007_auto_20181001_1200')
    ]

    operations = [
        migrations.RenameField(
            model_name='contract',
            old_name='force_rebalancing',
            new_name='rebalancing',
        ),
        migrations.RunPython(
            set_rebalancing,
            reverse_code=migrations.RunPython.noop
        ),
    ]
