from django.apps import AppConfig


class ETFKRConfig(AppConfig):
    name = 'api.bases.etf_kr'

    def ready(self):
        from common.db_routers import router
        router.add_mapping('etf_kr', 'etf_kr')
