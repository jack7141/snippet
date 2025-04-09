# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2021-06-18 05:41
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


def forward_func(apps, schema_editor):
    ManagementReport = apps.get_model("reports", "ManagementReport")
    db_alias = schema_editor.connection.alias
    ManagementReport.objects.using(db_alias).update(
        is_published=True
    )


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0002_update_report_return'),
    ]

    operations = [
        migrations.AddField(
            model_name='managementreport',
            name='is_published',
            field=models.BooleanField(default=False, help_text='발간 여부'),
        ),
        migrations.RunPython(
            forward_func, reverse_func
        ),

        migrations.AddField(
            model_name='assetuniverse',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, help_text='생성일'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='assetuniverse',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, help_text='수정일'),
        ),
        migrations.AddField(
            model_name='holdingdetail',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, help_text='생성일'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='holdingdetail',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, help_text='수정일'),
        ),
        migrations.AddField(
            model_name='managementreport',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, help_text='생성일'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='managementreport',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, help_text='수정일'),
        ),
        migrations.AddField(
            model_name='managementreportheader',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, help_text='생성일'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='managementreportheader',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, help_text='수정일'),
        ),
        migrations.AddField(
            model_name='managerdetail',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, help_text='생성일'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='managerdetail',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, help_text='수정일'),
        ),
        migrations.AddField(
            model_name='roboadvisordesc',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, help_text='생성일'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='roboadvisordesc',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, help_text='수정일'),
        ),
        migrations.AddField(
            model_name='tradingdetail',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, help_text='생성일'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='tradingdetail',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, help_text='수정일'),
        ),
    ]
