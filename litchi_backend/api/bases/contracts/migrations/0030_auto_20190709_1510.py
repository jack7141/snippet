# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-07-09 06:10
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


def migrate_contract_types(apps, schema_editor):
    ContractType = apps.get_model('contracts', 'contracttype')

    ContractType.objects.create(code='FA', name='펀드', fee_type=2, universe=1003, asset_type='kr_fund')
    ContractType.objects.create(code='EA', name='ETF', fee_type=2, reb_interval=30, universe=2013, asset_type='kr_etf')
    ContractType.objects.create(code='PA', name='연금', fee_type=2, date_method=2, universe=1051, asset_type='kr_fund')


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0029_auto_20190425_1615'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractType',
            fields=[
                ('code', models.CharField(help_text='관리코드', max_length=4, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='게약명', max_length=40)),
                ('universe', models.IntegerField(help_text='유니버스 코드')),
                ('asset_type', models.CharField(choices=[('kr_fund', '국내 펀드'), ('kr_etf', '국내 ETF'), ('etf', '해외 ETF')], help_text='상품에 포함 자산 종류 구분', max_length=8)),
                ('description', models.TextField(blank=True, help_text='계약 종류 설명', null=True)),
                ('fee_type', models.IntegerField(choices=[(1, '선취'), (2, '후취'), (3, '건당 결제'), (4, '무료')], help_text='보수 종류')),
                ('reb_interval', models.IntegerField(default=90, help_text='리밸런싱 발생 간격 일 수')),
                ('resend_interval', models.IntegerField(default=5, help_text='재전송 기준일 수')),
                ('delay_interval', models.IntegerField(default=0, help_text='지연실행 기준일 수')),
                ('date_method', models.IntegerField(choices=[(1, '일 기준'), (2, '영업일 기준')], default=1, help_text='일수 계산 방식')),
            ],
        ),
        migrations.RunPython(
            migrate_contract_types,
            reverse_code=migrations.RunPython.noop
        ),
        migrations.AlterField(
            model_name='contract',
            name='contract_type',
            field=models.ForeignKey(db_column='contract_type', help_text='계약종류', on_delete=django.db.models.deletion.PROTECT, related_name='contracts', to='contracts.ContractType'),
        ),
        migrations.AlterField(
            model_name='provisionalcontract',
            name='contract_type',
            field=models.ForeignKey(blank=True, db_column='contract_type', help_text='임시 계약종류', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='provisionals', to='contracts.ContractType'),
        ),
    ]
