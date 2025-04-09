from django.contrib import admin
from django.db.models import Count, Case, When, Q, Sum, Aggregate

from api.bases.notifications.models import Notification, Subscribe, Topic, Device
from api.bases.notifications.choices import NotificationChoices

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('topic', 'message', 'protocol', 'register', 'user', 'status', 'created_at',)
    list_filter = ('topic', 'protocol', 'created_at')
    search_fields = ('user__email', 'user__profile__name', 'user__profile__phone', 'message')
    raw_id_fields = ('user', 'register',)

    actions = ("send_message",)

    def send_message(self, request, queryset):
        for query in queryset:
            query.send_notification()

    send_message.short_description = "Re-send notification"


@admin.register(Subscribe)
class SubscribeAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'get_topics', 'created_at',)
    list_filter = ('type', 'topics')
    search_fields = ('user__email', 'user__profile__name', 'user__profile__phone')
    raw_id_fields = ('user',)

    def get_topics(self, obj):
        return ', '.join([str(topic) for topic in obj.topics.all()])

    get_topics.short_description = 'Topics'


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'subscribers')

    def subscribers(self, obj):
        ret = {}
        qs = obj.subscribe_set.all()

        for k, v in NotificationChoices.PROTOCOLS:
            ret.update(qs.aggregate(**{v: Count(Case(When(**{'type': k, 'then': 1})))}))

        return ret


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_id', 'active', 'user',)
    search_fields = ('user__email', 'user__profile__name', 'user__profile__phone')
    raw_id_fields = ('user',)
