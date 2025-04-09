from django.apps import AppConfig


class TendenciesConfig(AppConfig):
    name = 'api.bases.tendencies'

    def ready(self):
        import api.bases.tendencies.signals
