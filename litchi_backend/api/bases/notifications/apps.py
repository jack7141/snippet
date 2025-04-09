from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = 'api.bases.notifications'

    def ready(self):
        import api.bases.notifications.signals