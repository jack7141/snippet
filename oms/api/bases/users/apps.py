from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "api.bases.users"

    def ready(self):
        import api.bases.users.signals
