from django.apps import AppConfig


class AuthenticationsConfig(AppConfig):
    name = 'api.bases.authentications'

    def ready(self):
        import api.bases.authentications.signals