# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-03-19 08:52
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0026_auto_20190218_1432'),
    ]

    operations = [
        migrations.CreateModel(
            name='Extra',
            fields=[
                ('contract', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='contracts.Contract')),
                ('label', models.CharField(blank=True, help_text='구분', max_length=64, null=True)),
                ('target_date', models.DateTimeField(blank=True, help_text='목표 설정일', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='생성일')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='수정일')),
            ],
        ),
        migrations.AlterField(
            model_name='assetsdetail',
            name='balance',
            field=models.DecimalField(decimal_places=5, help_text='평가금액', max_digits=20),
        ),
        migrations.AlterField(
            model_name='assetsdetail',
            name='buy_price',
            field=models.DecimalField(decimal_places=5, help_text='구매가', max_digits=20),
        ),
        migrations.AlterField(
            model_name='assetsdetail',
            name='code',
            field=models.CharField(help_text='ISIN', max_length=12),
        ),
        migrations.AlterField(
            model_name='assetsdetail',
            name='shares',
            field=models.IntegerField(help_text='좌수'),
        ),
    ]
