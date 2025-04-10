# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2022-09-30 06:33
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0044_add_default_term_detail'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='term_detail',
            field=models.ForeignKey(blank=True, help_text='약관 상세 조건', null=True, on_delete=django.db.models.deletion.CASCADE, to='contracts.TermDetail'),
        ),
        migrations.AlterField(
            model_name='termdetail',
            name='amount',
            field=models.IntegerField(blank=True, default=0, help_text='수수료액', null=True,
                                      validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='termdetail',
            name='period_int',
            field=models.IntegerField(blank=True, default=0, help_text='무료 적용 기간(정수)', null=True,
                                      validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AlterField(
            model_name='termdetail',
            name='rate',
            field=models.FloatField(blank=True, default=0, help_text='수수료율', null=True,
                                    validators=[django.core.validators.MinValueValidator(0),
                                                django.core.validators.MaxValueValidator(1)]),
        ),
    ]
