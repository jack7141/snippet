from django.apps import AppConfig


class PortfolioConfig(AppConfig):
    name = 'api.bases.portfolios'

    def ready(self):
        from common.db_routers import router
        router.add_mapping('portfolios', 'bluewhale')
