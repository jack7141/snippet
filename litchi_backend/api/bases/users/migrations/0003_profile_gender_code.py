# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-03-20 09:17
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_profile_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='gender_code',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Local Male(1)'), (2, 'Local Female(2)'), (3, 'Local Male(3)'), (4, 'Local Female(4)'), (5, 'Foreign Male(5)'), (6, 'Foreign Female(6)'), (7, 'Foreign Male(7)'), (8, 'Foreign Female(8)'), (9, 'Local Male(9)'), (0, 'Local Female(10)')], max_length=1, null=True),
        ),
    ]
