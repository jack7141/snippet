from django.apps import AppConfig


class PortfolioConfig(AppConfig):
    name = "api.bases.portfolio"

    def ready(self):
        from common.db_routers import router

        router.add_mapping("portfolio", "portfolio")
