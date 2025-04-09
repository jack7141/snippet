from django.apps import AppConfig


class InfomaxConfig(AppConfig):
    name = 'api.bases.infomax'

    def ready(self):
        from common.db_routers import router
        router.add_mapping('infomax', 'infomax')
