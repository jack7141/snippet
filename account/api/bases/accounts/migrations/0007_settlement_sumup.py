# Generated by Django 3.0.3 on 2021-06-15 03:12

import django.utils.timezone
import model_utils.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_execution'),
    ]

    operations = [
        migrations.CreateModel(
            name='SumUp',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                   help_text='생성일')),
                ('updated_at',
                 model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                          help_text='수정일')),
                ('j_name', models.CharField(blank=True, help_text='적요명', max_length=35, null=True)),
                ('j_code', models.CharField(blank=True, help_text='적요유형코드', max_length=3, null=True)),
                ('amount_func_type', models.CharField(blank=True, choices=[('INPUT', '원화 입금'), ('OUTPUT', '원화 출금'),
                                                                           ('OUTPUT_USD', '외화 출금'), ('IMPORT', '입고'),
                                                                           ('EXPORT', '출고'),
                                                                           ('DIVIDEND_INPUT', '배당금 입금'),
                                                                           ('OVERSEA_TAX', '해외 수수료')], max_length=30,
                                                      null=True)),
                ('trade_type', models.CharField(blank=True, choices=[('INPUT', '원화 입금'), ('OUTPUT', '원화 출금'),
                                                                     ('OUTPUT_USD', '외화 출금'), ('IMPORT', '입고'),
                                                                     ('EXPORT', '출고'), ('DIVIDEND_INPUT', '배당금 입금'),
                                                                     ('OVERSEA_TAX', '해외 수수료'), ('BID', '매수'),
                                                                     ('ASK', '매도'), ('SETTLEMENT_IN', '정산(입금)'),
                                                                     ('SETTLEMENT_OUT', '정산(출금)'), ('EXCHANGE', '환전'),
                                                                     ('INTEREST_DEPOSIT', '이자 입금')], max_length=30,
                                                null=True)),
                ('managed', models.BooleanField(default=False, help_text='관리여부')),
                ('description', models.CharField(blank=True, help_text='설명', max_length=100, null=True)),
            ],
            options={
                'unique_together': {('j_name', 'j_code')},
            },
        ),
        migrations.CreateModel(
            name='Settlement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                   help_text='생성일')),
                ('updated_at',
                 model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                          help_text='수정일')),
                ('base', models.BigIntegerField(default=0, help_text='투자원금')),
                ('deposit', models.BigIntegerField(default=0, help_text='원화 예수금 잔고(KRW)')),
                ('for_deposit',
                 models.DecimalField(decimal_places=4, default=0, help_text='외화 예수금 잔고(USD)', max_digits=15)),
                ('input_amt', models.BigIntegerField(default=0, help_text='입금액')),
                ('output_amt', models.BigIntegerField(default=0, help_text='출금액')),
                ('import_amt', models.DecimalField(decimal_places=4, default=0, help_text='입고계', max_digits=15)),
                ('export_amt', models.DecimalField(decimal_places=4, default=0, help_text='출고계', max_digits=15)),
                ('dividend', models.DecimalField(decimal_places=4, help_text='배당금(세후)', max_digits=15, null=True)),
                ('dividend_input_amt',
                 models.DecimalField(decimal_places=4, help_text='배당금(세전)', max_digits=15, null=True)),
                ('commission', models.DecimalField(decimal_places=4, help_text='국내 수수료', max_digits=15)),
                ('in_come_tax', models.DecimalField(decimal_places=4, help_text='국내 소득세', max_digits=15)),
                ('reside_tax', models.DecimalField(decimal_places=4, help_text='주민세', max_digits=15)),
                ('settled_for_amt',
                 models.DecimalField(decimal_places=4, help_text='당일 결제 대금(USD, 세전)', max_digits=15, null=True)),
                ('unsettled_for_amt',
                 models.DecimalField(decimal_places=4, help_text='외화 미결제대금 잔고(USD, 세전)', max_digits=15)),
                ('for_trd_tax', models.DecimalField(decimal_places=4, help_text='미결제 해외 거래 세금(USD)', max_digits=15)),
                ('for_commission', models.DecimalField(decimal_places=4, help_text='미결제 국외수수료(USD)', max_digits=15)),
                ('account_alias', models.ForeignKey(help_text='계좌번호 별칭', on_delete=django.db.models.deletion.CASCADE,
                                                    to='accounts.Account')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
