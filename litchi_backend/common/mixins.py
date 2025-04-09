import json
import logging
import requests

from urllib.parse import urljoin

logger = logging.getLogger('django.server')


class AdapterMixin(object):
    def get_header(self):
        return {
            'Authorization': 'Token ' + self.token,
            'Content-Type': 'application/json'
        }

    def request(self, additional_url, data=None, method="POST"):
        url = urljoin(self.base, additional_url)
        data = json.dumps(data) if data is not None else dict()
        response = requests.request(
            method,
            url,
            headers=self.get_header(),
            data=data
        )

        if not response:
            logger.warning(
                'received the error response. %s %s %s %s - %s' %
                (method, url, response.status_code, len(response.content), response.text))

        return response
