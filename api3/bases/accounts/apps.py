from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'api.bases.accounts'

    def ready(self):
        import api.bases.accounts.signals
