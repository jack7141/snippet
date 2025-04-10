# Generated by Django 3.0.3 on 2021-06-02 05:55

import django.utils.timezone
import model_utils.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_trade'),
    ]

    operations = [
        migrations.CreateModel(
            name='Execution',
            fields=[
                ('created_at', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False,
                                                                   help_text='생성일')),
                ('updated_at',
                 model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False,
                                                          help_text='수정일')),
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('order_date', models.DateField(help_text='체결일자')),
                ('ord_no', models.IntegerField(help_text='주문번호')),
                ('code_name', models.CharField(help_text='종목명', max_length=40, null=True)),
                ('code', models.CharField(help_text='단축종목코드', max_length=12, null=True)),
                ('trade_sec_name', models.CharField(help_text='거래구분명', max_length=8, null=True)),
                ('order_status', models.CharField(help_text='주문상태명', max_length=8, null=True)),
                ('exec_qty', models.IntegerField(help_text='체결수량')),
                ('exec_price', models.DecimalField(decimal_places=4, help_text='체결수량', max_digits=15)),
                ('ord_qty', models.IntegerField(help_text='주문수량')),
                ('ord_price', models.DecimalField(decimal_places=4, help_text='주문수량', max_digits=15)),
                ('unexec_qty', models.IntegerField(help_text='미체결수량', null=True)),
                ('org_ord_no', models.IntegerField(help_text='원주문번호', null=True)),
                ('mkt_clsf_nm', models.CharField(help_text='시장구분명', max_length=10)),
                ('currency_code', models.CharField(help_text='통화코드', max_length=3, null=True)),
                ('ord_sec_name', models.CharField(help_text='주문구분명', max_length=10, null=True)),
                ('from_time', models.TimeField(help_text='시작시간', null=True)),
                ('to_time', models.TimeField(help_text='종료시간', null=True)),
                ('order_tool_name', models.CharField(help_text='주문매체명', max_length=50)),
                ('order_time', models.TimeField(help_text='주문시간', null=True)),
                ('aplc_excj_rate', models.DecimalField(decimal_places=4, help_text='적용환율', max_digits=9)),
                ('reject_reason', models.CharField(help_text='거부사유', max_length=100, null=True)),
                ('ex_code', models.CharField(help_text='해외거래소구분코드', max_length=3, null=True)),
                ('loan_date', models.CharField(help_text='대출일자', max_length=8, null=True)),
                ('org_price', models.DecimalField(decimal_places=4, help_text='주문가격', max_digits=15)),
                ('exchange_rate', models.DecimalField(decimal_places=4, help_text='환율', max_digits=9)),
                ('frgn_stp_prc', models.DecimalField(decimal_places=4, help_text='해외중단가격(P4)', max_digits=16)),
                ('frgn_brkr_ccd', models.CharField(help_text='해외브로커구분코드', max_length=2, null=True)),
                ('account_alias', models.ForeignKey(help_text='계좌번호 별칭', on_delete=django.db.models.deletion.CASCADE,
                                                    to='accounts.Account')),
            ],
            options={
                'unique_together': {('account_alias', 'order_date', 'ord_no')},
            },
        ),
    ]
