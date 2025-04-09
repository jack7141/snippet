from django.apps import AppConfig

from django.utils import timezone


class ContractsConfig(AppConfig):
    name = 'api.bases.contracts'

    def ready(self):
        import api.bases.contracts.signals