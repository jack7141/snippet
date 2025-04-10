# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-12-11 02:16
from __future__ import unicode_literals

from django.db import migrations, models


def migrate_subscribe_notification_topic(apps, schema_editor):
    Subscribe = apps.get_model('notifications', 'subscribe')
    Topic = apps.get_model('notifications', 'topic')
    User = apps.get_model('users', 'user')

    topic = Topic.objects.get(name='notification')

    for user in User.objects.all():
        for protocol in ["2", "4"]:
            sub_instance, _ = Subscribe.objects.get_or_create(
                user=user,
                type=protocol
            )
            sub_instance.topics.add(topic)


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0007_auto_20181211_1116'),
    ]

    operations = [
        migrations.RunPython(
            migrate_subscribe_notification_topic,
            reverse_code=migrations.RunPython.noop
        ),
    ]
