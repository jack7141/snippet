# Generated by Django 3.0.3 on 2022-12-14 09:02

import api.bases.accounts.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_add_account_pension'),
    ]

    operations = [
        migrations.AddField(
            model_name='amounthistory',
            name='stock_export_amt',
            field=models.DecimalField(decimal_places=4, default=0, help_text='출고 총계', max_digits=15),
        ),
        migrations.AddField(
            model_name='amounthistory',
            name='stock_import_amt',
            field=models.DecimalField(decimal_places=4, default=0, help_text='입고 총계', max_digits=15),
        ),
        migrations.AddField(
            model_name='amounthistory',
            name='stock_transfer_amt',
            field=models.DecimalField(decimal_places=4, default=0, help_text='입출고 총계', max_digits=15),
        ),
    ]
