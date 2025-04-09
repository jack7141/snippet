from django.apps import AppConfig


class OrdersConfig(AppConfig):
    name = "api.bases.orders"

    def ready(self):
        import api.bases.orders.signals
        from common.db_routers import router

        router.add_mapping("orders", "accounts")
