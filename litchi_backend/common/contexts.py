import logging
from typing import Type
from enum import auto
from common.utils import StrEnum
from collections import OrderedDict

logger = logging.getLogger('django.server')

DELIMITER = '-'
TEMPLATE_KWARGS = OrderedDict.fromkeys(['prefix', 'product_code', 'topic', 'status', 'step'], '')
TEMPLATE_ID_FORMAT = DELIMITER.join([
    "{" + k + "}" for k in TEMPLATE_KWARGS.keys()
])


class Prefix(StrEnum):
    key = 'prefix'

    SYSTEM = 'SYSTEM'


class NotiTopic(StrEnum):
    key = 'topic'

    ACCOUNT_OPENED = auto()
    NEW_ORDER = auto()
    REBALANCING = auto()
    CONTRACT_CANCELLATION = auto()
    CONTRACT_EXPIRATION = auto()
    CONTRACT_RENEWAL = auto()
    ACCOUNT_TRANSFER = auto()
    ACCOUNT_SUSPENTION = auto()


class NotiStatus(StrEnum):
    key = 'status'

    IS_STARTED = auto()
    IS_COMPLETE = auto()
    IS_STAND_BY = auto()
    IS_CANCELED = auto()


class NotiStep(StrEnum):
    key = 'step'

    STEP1 = auto()
    STEP2 = auto()


class ProductCode(StrEnum):
    key = 'product_code'

    PA = auto()
    EA = auto()
    FA = auto()
    OEA = auto()
    KBPA = auto()
    MOEA = auto()


class ContextFields(StrEnum):
    product_name = auto()  # 상품명
    expiry_date = auto()  # 계약만료일
    canceled_date = auto()  # 계약해지일
    vendor_name = auto()  # 증권사
    opponent_vendor_name = auto()  # 상대 증권사 (예 : 연금이전 - 연금 가입된 증권사)
    advisor_fee = auto()  # 수수료 금액
    account_number = auto()  # 계좌 번호
    opponent_account_number = auto()  # 상대 계좌 번호 (예 : 연금이전 - 연금 가입할 증권사)
    analysis_result = auto()  # 투자성향 결과
    analysis_date = auto()  # 투자성향 날짜
    last_day = auto()  # 투자성향 일
    last_month = auto()  # 투자성향 월


CONSULTING_PRODUCTS = [
    ProductCode.PA, ProductCode.FA, ProductCode.EA, ProductCode.KBPA
]

ALL_INV_PRODUCTS = [
                       ProductCode.OEA,
                       ProductCode.MOEA,
                   ] + CONSULTING_PRODUCTS

SYSTEM_TEMPLATE_MESSAGE_FIELDS = {
    NotiTopic.ACCOUNT_OPENED: {  # topic
        NotiStatus.IS_COMPLETE: {  # status
            k: {NotiStep.STEP1: [ContextFields.product_name,
                                 ContextFields.account_number,
                                 ContextFields.vendor_name]} for k in ALL_INV_PRODUCTS
        }
    },
    NotiTopic.NEW_ORDER: {
        NotiStatus.IS_STARTED: {
            k: {NotiStep.STEP1: [ContextFields.product_name]} for k in ALL_INV_PRODUCTS
        },
        NotiStatus.IS_COMPLETE: {
            k: {NotiStep.STEP1: [ContextFields.product_name]} for k in ALL_INV_PRODUCTS
        }
    },
    NotiTopic.REBALANCING: {
        NotiStatus.IS_STAND_BY: {
            ProductCode.FA: {
                NotiStep.STEP1: [ContextFields.product_name],
            },
            ProductCode.PA: {
                NotiStep.STEP1: [ContextFields.product_name],
            },
            ProductCode.KBPA: {
                NotiStep.STEP1: [ContextFields.product_name],
            },
            ProductCode.EA: {
                NotiStep.STEP1: [ContextFields.product_name],
                NotiStep.STEP2: [ContextFields.product_name],
            }
        },
        NotiStatus.IS_COMPLETE: {
            ProductCode.FA: {
                NotiStep.STEP1: [ContextFields.product_name]
            },
            ProductCode.PA: {
                NotiStep.STEP1: [ContextFields.product_name]
            },
            ProductCode.KBPA: {
                NotiStep.STEP1: [ContextFields.product_name]
            },
            ProductCode.EA: {
                NotiStep.STEP2: [ContextFields.product_name]
            }
        }
    },
    NotiTopic.CONTRACT_CANCELLATION: {
        NotiStatus.IS_STAND_BY: {
            ProductCode.FA: {
                NotiStep.STEP1: [ContextFields.product_name],
            },
            ProductCode.PA: {
                NotiStep.STEP1: [ContextFields.product_name],
            },
            ProductCode.KBPA: {
                NotiStep.STEP1: [ContextFields.product_name],
            },
            ProductCode.EA: {
                NotiStep.STEP1: [ContextFields.product_name],
            },
            ProductCode.MOEA: {
                NotiStep.STEP1: [ContextFields.product_name],
            }
        },
        NotiStatus.IS_STARTED: {
            ProductCode.OEA: {
                NotiStep.STEP1: [ContextFields.product_name]
            },
            ProductCode.MOEA: {
                NotiStep.STEP1: [ContextFields.product_name]
            }
        },
        NotiStatus.IS_COMPLETE: {
            ProductCode.FA: {
                NotiStep.STEP1: [ContextFields.product_name,
                                 ContextFields.advisor_fee,
                                 ContextFields.vendor_name],
            },
            ProductCode.PA: {
                NotiStep.STEP1: [ContextFields.product_name,
                                 ContextFields.advisor_fee,
                                 ContextFields.vendor_name],
            },
            ProductCode.KBPA: {
                NotiStep.STEP1: [ContextFields.product_name,
                                 ContextFields.advisor_fee,
                                 ContextFields.vendor_name],
            },
            ProductCode.EA: {
                NotiStep.STEP1: [ContextFields.product_name,
                                 ContextFields.advisor_fee,
                                 ContextFields.vendor_name],
            },
            ProductCode.OEA: {
                NotiStep.STEP1: [ContextFields.product_name,
                                 ContextFields.advisor_fee,
                                 ContextFields.vendor_name],
            },
            ProductCode.MOEA: {
                NotiStep.STEP1: [ContextFields.product_name,
                                 ContextFields.advisor_fee,
                                 ContextFields.vendor_name],
            }
        }
    },
    NotiTopic.ACCOUNT_TRANSFER: {
        NotiStatus.IS_STARTED: {
            ProductCode.KBPA: {
                NotiStep.STEP1: [ContextFields.opponent_vendor_name,
                                 ContextFields.opponent_account_number,
                                 ContextFields.vendor_name,
                                 ContextFields.account_number]
            }
        },
        NotiStatus.IS_COMPLETE: {
            ProductCode.KBPA: {
                NotiStep.STEP1: []
            }
        },
        NotiStatus.IS_CANCELED: {
            ProductCode.KBPA: {
                NotiStep.STEP1: [ContextFields.opponent_vendor_name,
                                 ContextFields.opponent_account_number,
                                 ContextFields.vendor_name,
                                 ContextFields.account_number]
            }
        }
    },
    NotiTopic.ACCOUNT_SUSPENTION: {
        NotiStatus.IS_STARTED: {
            ProductCode.OEA: {
                NotiStep.STEP1: [ContextFields.product_name,
                                 ContextFields.analysis_result,
                                 ContextFields.analysis_date,
                                 ContextFields.last_day,
                                 ContextFields.last_month]
            },
            ProductCode.MOEA: {
                NotiStep.STEP1: [ContextFields.product_name,
                                 ContextFields.analysis_result,
                                 ContextFields.analysis_date,
                                 ContextFields.last_day,
                                 ContextFields.last_month]
            }
        }
    }
}


def acct_masking(acct_no, mask_len=4):
    return "".join((acct_no[:3], "*" * mask_len, acct_no[3 + mask_len:]))


def format_vendor_acct(vendor_acct, vendor_code):
    """
    :param vendor_acct: vendor account number
    :param vendor_code: vendor code

    :return: formatted vendor account number or didn't formatted account number
    """
    return {
        "hanaw": "{}-{}".format(vendor_acct[:8], vendor_acct[8:]),
        "shinhan": "{}-{}-{}".format(vendor_acct[:3], vendor_acct[3:5], vendor_acct[5:]),
        "kb": "{}-{}-{}-{}".format(vendor_acct[:3], vendor_acct[3:6], vendor_acct[6:9], vendor_acct[9:]),

    }.get(vendor_code, vendor_acct)


def parse_template_fields(root, comps=None):
    if comps is None:
        comps = [Prefix.SYSTEM]

    res = []
    if isinstance(root, dict):
        for k, v in root.items():
            comps.append(k)
            res += parse_template_fields(root=v, comps=comps)
            comps.pop()
    elif isinstance(root, list):
        return [(TEMPLATE_ID_FORMAT.format(**{enum.key: enum for enum in comps}), root)]
    return res


class MessageContext:
    def __init__(self, factory: 'MessageContextFactory', topic='', status='', step='', product_code='', **kwargs):
        self._factory = factory
        self.context_fields = kwargs['context_fields'] if 'context_fields' in kwargs else {}
        self._template_fields = {'prefix': Prefix.SYSTEM}
        self._topic = topic
        self._status = status
        self._step = step
        self._product_code = product_code

    @property
    def template_id(self):
        _template_fields = self.get_template_fields()
        return self._factory.get_template_id(**{k: v for k, v in _template_fields.items() if v})

    @property
    def product_code(self):
        return self._product_code

    def is_predefined(self):
        return bool(self.product_code and self._topic and self._status and self._step)

    def get_template_fields(self):
        _template_fields = self._template_fields.copy()
        if self.is_predefined():
            _template_fields.update({
                'product_code': self.product_code,
                'topic': self._topic,
                'status': self._status,
                'step': self._step
            })
        return _template_fields

    def to_dict(self):
        _context = {
            'template_id': self.template_id,
            **self.context_fields
        }
        return _context


class MessageContextFactory:
    template_map = OrderedDict(parse_template_fields(root=SYSTEM_TEMPLATE_MESSAGE_FIELDS))

    def __init__(self, context_class: Type[MessageContext]):
        self.context_class = context_class

    def get_field_names(self, template_id: str):
        return [f.value for f in self.template_map.get(template_id)]

    def get_context_dic(self, instance, topic='', status='', step='', product_code='', **kwargs) -> dict:
        try:
            _context = self.get_context(instance=instance,
                                        topic=topic,
                                        status=status,
                                        step=step,
                                        product_code=product_code,
                                        **kwargs)
            if _context.template_id:
                return _context.to_dict()
        except KeyError as e:
            logger.warning(f"Key error: {e}")
        return {}

    def get_context(self, instance, topic='', status='', step='', product_code='', **kwargs) -> MessageContext:
        _context: MessageContext = self.context_class(instance=instance,
                                                      factory=self,
                                                      topic=topic,
                                                      status=status,
                                                      step=step,
                                                      product_code=product_code,
                                                      **kwargs)
        _template_id = _context.template_id
        if not self.is_registered(_template_id):
            raise KeyError(f"Unregistered template_id: {_template_id}")

        for f in self.get_field_names(_template_id):
            if f not in _context.context_fields:
                _context.context_fields[f] = getattr(_context, f, '')
        return _context

    @classmethod
    def is_registered(cls, template_id):
        return template_id in cls.template_map

    @staticmethod
    def get_template_id(topic='', status='', product_code='', step='', prefix=Prefix.SYSTEM):
        return TEMPLATE_ID_FORMAT.format(prefix=prefix, topic=topic, status=status,
                                         product_code=product_code, step=step)
