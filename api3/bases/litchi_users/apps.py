from django.apps import AppConfig


class LitchiUserConfig(AppConfig):
    name = 'api.bases.litchi_users'

    def ready(self):
        from common.db_routers import router
        router.add_mapping('litchi_users', 'litchi')
