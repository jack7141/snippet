import logging
from litchi_backend.celery import app
from api.bases.contracts.models import Contract


logger = logging.getLogger('django.server')


@app.task
def set_acct_nickname(contract_id, vendor_code):
    try:
        instance = Contract.objects.get(pk=contract_id)
        endpoint = '/api/v1/{}/account/nickname'.format(vendor_code)

        instance.get_realtime_data('realtime', endpoint, **{
            "accts": [
                {
                    "acct_number": instance.account_number,
                    "acct_seq": "100",
                    "acct_nick_name": f"파운트 {instance.user.profile.name}"
                }
            ]
        })
    except Contract.DoesNotExist as e:
        logger.warning(f"Fail to find contract, detail: {e}")
    except Exception as e:
        logger.error(f"Unexpected error, detail: {e}")
