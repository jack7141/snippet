from django.apps import AppConfig


class OrdersConfig(AppConfig):
    name = 'api.bases.orders'

    def ready(self):
        import api.bases.orders.signals
