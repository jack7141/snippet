from django.apps import AppConfig


class UserConfig(AppConfig):
    name = 'api.bases.users'

    def ready(self):
        import api.bases.users.signals
