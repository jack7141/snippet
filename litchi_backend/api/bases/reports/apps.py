from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = 'api.bases.reports'

    def ready(self):
        from common.db_routers import router
        router.add_mapping('reports', 'wealth_management')
