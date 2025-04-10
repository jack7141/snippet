# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-12-11 04:55
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.utils import timezone


def create_rebalancing(apps, schema_editor):
    Order = apps.get_model('orders', 'order')
    Rebalancing = apps.get_model('contracts', 'rebalancing')

    for item in Order.objects.all().order_by('created_at'):
        if item.mode == 'rebalancing':
            rebalancing = Rebalancing.objects.create(contract=item.order_item)
            rebalancing.sold_at = item.created_at
            rebalancing.bought_at = item.created_at
            rebalancing.save()
        elif item.mode == 'sell':
            rebalancing = Rebalancing.objects.create(contract=item.order_item)
            rebalancing.sold_at = item.created_at
            rebalancing.save()
        elif item.mode == 'buy':
            rebalancing = Rebalancing.objects.filter(contract=item.order_item).latest('created_at')
            rebalancing.bought_at = item.created_at
            rebalancing.save()


def uncreate_rebalancing(apps, schema_editor):
    Contract = apps.get_model('contracts', 'contract')
    Rebalancing = apps.get_model('contracts', 'rebalancing')


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0007_auto_20181211_1116'),
        ('contracts', '0023_contract_cancel_reason'),
    ]

    operations = [
        migrations.CreateModel(
            name='Rebalancing',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='생성일')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='수정일')),
                ('sold_at', models.DateTimeField(blank=True, help_text='매도일', null=True)),
                ('bought_at', models.DateTimeField(blank=True, help_text='매수일', null=True)),
                ('contract', models.ForeignKey(help_text='계약', on_delete=django.db.models.deletion.CASCADE, related_name='rebs', to='contracts.Contract')),
                ('notifications', models.ManyToManyField(help_text='알람 발생 목록', related_name='rebs', to='notifications.Notification')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.RunPython(
            create_rebalancing,
            reverse_code=uncreate_rebalancing
        ),
    ]
