from django.conf import settings
from common.designpatterns import SingletonClass


# class BacktestConnector(Celery, SingletonClass):
#     def __init__(self):
#         broker = settings.BACKTEST_BROKER_URL
#         backend = settings.BACKTEST_RESULT_BACKEND
#
#         super(BacktestConnector, self).__init__(broker=broker, backend=backend)
