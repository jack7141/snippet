from ast import literal_eval as make_tuple
from celery import task
from celery.utils.log import get_task_logger
import redis

from common.utils import send_mass_html_mail
from litchi_backend import settings

logger = get_task_logger(__name__)


def set_email_tuple(datatuple):
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    r.append('email_datatuple_list', datatuple)


def get_email_tuple():
    r = redis.StrictRedis(host='localhost', port=6379, db=0)

    pipe = r.pipeline()
    pipe.get('email_datatuple_list')
    pipe.delete('email_datatuple_list')
    result = pipe.execute()
    datatuple = result[0]

    if datatuple is None:
        datatuple = list()
    else:
        datatuple = make_tuple(datatuple.decode('UTF-8'))

    return datatuple


def send_mass_email_html(datatuple, is_async=True):
    if settings.USE_CELERY is True:
        task_send_async_email.delay(datatuple, is_async=is_async)
    else:
        send_mass_html_mail(datatuple)


@task
def task_send_async_email(datatuple, is_async=True):
    if is_async is True:
        send_mass_html_mail(datatuple)
    else:
        set_email_tuple(datatuple)


@task
def task_send_queue_email():
    datatuple = get_email_tuple()
    send_mass_html_mail(datatuple)
