from django.apps import AppConfig


class FundsConfig(AppConfig):
    name = 'api.bases.funds'

    def ready(self):
        from common.db_routers import router
        router.add_mapping('funds', 'fund')
