# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-08-28 02:30
from __future__ import unicode_literals

from django.db import migrations, models


def set_status(apps, schema_editor):
    Contract = apps.get_model('contracts', 'contract')
    Contract.objects.filter(is_canceled=True).update(status=0)


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0013_auto_20180730_0439'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='status',
            field=models.IntegerField(choices=[(0, '해지됨'), (1, '정상 유지'), ('Firmbanking', [(2, '펌뱅킹 등록 중'), (20, '펌뱅킹 등록 실패'), (21, '펌뱅킹 등록 완료')]), ('Withdraw', [(3, '출금이체 진행 중'), (30, '출금이체 실패'), (31, '출금이체 완료')])], default=1),
        ),
        migrations.RunPython(
            set_status,
            reverse_code=migrations.RunPython.noop
        ),
    ]
