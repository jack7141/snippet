from django.apps import AppConfig


class SmsConfig(AppConfig):
    name = 'api.bases.sms'

    def ready(self):
        from common.db_routers import router
        router.add_mapping('sms', 'sms')

