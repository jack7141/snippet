# Generated by Django 3.0.3 on 2021-04-05 09:00

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_account_risk_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='portfolio_id',
        ),
    ]
