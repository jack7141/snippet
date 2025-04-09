import json
from json import JSONDecodeError

from elasticapm.conf.constants import ERROR, TRANSACTION

from elasticapm.utils import varmap
from elasticapm.utils.encoding import force_text
from elasticapm.processors import for_events, _sanitize


@for_events(ERROR, TRANSACTION)
def sanitize_http_request_json_body(client, event):
    """
    Sanitizes http request body.
    This only works if the request body is JSON objects

    :param client: an ElasticAPM client
    :param event: a transaction or error event
    :return: The modified event
    """
    try:
        body = json.loads(force_text(event["context"]["request"]["body"], errors="replace"))
        event["context"]["request"]["body"] = json.dumps(
            varmap(_sanitize, body, sanitize_field_names=client.config.sanitize_field_names)
        )
    except (KeyError, TypeError):
        pass
    except JSONDecodeError:
        pass

    return event
