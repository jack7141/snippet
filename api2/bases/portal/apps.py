from django.apps import AppConfig


class PortalConfig(AppConfig):
    name = "api.bases.portal"

    def ready(self):
        from common.db_routers import router

        router.add_mapping("portal", "portal")
