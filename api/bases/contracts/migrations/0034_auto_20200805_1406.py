# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2020-08-05 05:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0033_contracttype_operation_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='condition',
            name='volume_path',
            field=models.CharField(blank=True, help_text='증권사 계약 문서 저장 볼륨', max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name='condition',
            name='doc_path',
            field=models.CharField(blank=True, help_text='증권사 계약 문서 경로', max_length=128, null=True),
        ),
        migrations.AlterField(
            model_name='contract',
            name='status',
            field=models.IntegerField(choices=[(0, '해지됨'), (1, '정상 유지'), ('Firmbanking', [(2, '펌뱅킹 등록 중'), (20, '펌뱅킹 등록 실패'), (21, '펌뱅킹 등록 완료')]), ('Withdraw', [(3, '출금이체 진행 중'), (30, '출금이체 실패'), (31, '출금이체 완료')]), ('Vendor', [(4, '협력사 해지 대기'), (41, '협력사 계좌개설 대기'), (42, '주문대리인 등록 대기'), (43, '인증토큰 발급 실패'), (44, '증권사 식별정보 조회 실패'), (45, '전자문서 전달 실패'), (46, '주문대리인 등록 실패')])], default=41, help_text='계약 상태'),
        ),
        migrations.AlterField(
            model_name='contracttype',
            name='operation_type',
            field=models.CharField(choices=[('A', '자문'), ('D', '일임')], default='A', help_text='자문/일임 구분', max_length=1),
        ),
    ]
