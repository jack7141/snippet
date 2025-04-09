from django.apps import AppConfig


class ETFUSConfig(AppConfig):
    name = 'api.bases.etf_us'

    def ready(self):
        from common.db_routers import router
        router.add_mapping('etf_us', 'etf_us')
