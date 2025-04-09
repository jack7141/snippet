import logging

from requests_toolbelt.utils import dump

logger = logging.getLogger(__name__)


def log_response(response, *args, **kwargs) -> None:
    data = dump.dump_all(response)
    logger.info(data.decode("utf-8").replace("\r\n", " "))
