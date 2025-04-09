from model_utils import Choices

from api.bases.contracts.choices import ContractChoices
from api.bases.notifications.choices import NotificationsSettings


class Risk:
    RISK_NAMES = ['안정형', '안정추구형', '중립형', '성장형', '공격형']


class Messages:
    _MODES = ContractChoices.ORDER_MODES
    _STATUS = ContractChoices.ORDER_STATUS

    MESSAGE_TEMPLATES = {
        'sms': {
            _MODES.new_order: {
                _STATUS.processing: '매수 신청이 성공적으로 완료되었습니다.',
                _STATUS.completed: '매수가 완료되었습니다.',
                _STATUS.skipped: '매수가 완료되었습니다.',
            },
            _MODES.sell: {
                _STATUS.on_hold: '리밸런싱 발생. 앱에서 매도를 실행해주세요. {}'.format(NotificationsSettings.APP_LINK_URL),
                _STATUS.processing: '리밸런싱 매도 신청이 성공적으로 완료되었습니다.'
            },
            _MODES.buy: {
                _STATUS.on_hold: '리밸런싱(매도) 완료. 앱에서 매수를 실행해주세요. {}'.format(NotificationsSettings.APP_LINK_URL),
                _STATUS.processing: '리밸런싱 매수 신청이 성공적으로 완료되었습니다.',
                _STATUS.completed: '리밸런싱 완료. 앱에서 확인하세요. {}'.format(NotificationsSettings.APP_LINK_URL),
                _STATUS.skipped: '리밸런싱 완료. 앱에서 확인하세요. {}'.format(NotificationsSettings.APP_LINK_URL),
            },
            _MODES.rebalancing: {
                _STATUS.on_hold: '리밸런싱 발생. 앱에서 실행해주세요. {}'.format(NotificationsSettings.APP_LINK_URL),
                _STATUS.processing: '리밸런싱 신청이 성공적으로 완료되었습니다.',
                _STATUS.completed: '리밸런싱 완료. 앱에서 확인하세요. {}'.format(NotificationsSettings.APP_LINK_URL),
                _STATUS.skipped: '리밸런싱 완료. 앱에서 확인하세요. {}'.format(NotificationsSettings.APP_LINK_URL),
            },
        },
        'push': {
            _MODES.new_order: {
                _STATUS.processing: '매수 신청이 성공적으로 완료되었습니다.',
                _STATUS.completed: '매수가 완료되었습니다.',
                _STATUS.skipped: '매수가 완료되었습니다.',
            },
            _MODES.sell: {
                _STATUS.on_hold: '리밸런싱이 발생했습니다. 리밸런싱 매도를 실행하세요.',
                _STATUS.processing: '리밸런싱 매도 신청이 성공적으로 완료되었습니다.'
            },
            _MODES.buy: {
                _STATUS.on_hold: '리밸런싱 매도가 완료되었습니다. 리밸런싱 매수를 실행하세요.',
                _STATUS.processing: '리밸런싱 매수 신청이 성공적으로 완료되었습니다.',
                _STATUS.completed: '리밸런싱이 완료되었습니다.',
                _STATUS.skipped: '리밸런싱이 완료되었습니다.',
            },
            _MODES.rebalancing: {
                _STATUS.on_hold: '리밸런싱이 발생했습니다.',
                _STATUS.processing: '리밸런싱 신청이 성공적으로 완료되었습니다.',
                _STATUS.completed: '리밸런싱이 완료되었습니다.',
                _STATUS.skipped: '리밸런싱이 완료되었습니다.',
            },
        },
        'app': {
            _MODES.new_order: {
                _STATUS.processing: '매수 신청이 성공적으로 완료되었습니다.',
                _STATUS.completed: '매수가 완료되었습니다.',
                _STATUS.skipped: '매수가 완료되었습니다.',
            },
            _MODES.sell: {
                _STATUS.on_hold: '리밸런싱이 발생했습니다.',
                _STATUS.processing: '리밸런싱 매도 신청이 성공적으로 완료되었습니다.'
            },
            _MODES.buy: {
                _STATUS.on_hold: '리밸런싱 매도가 완료되었습니다. 리밸런싱 매수를 실행하세요.',
                _STATUS.processing: '리밸런싱 매수 신청이 성공적으로 완료되었습니다.',
                _STATUS.completed: '리밸런싱이 완료되었습니다.',
                _STATUS.skipped: '리밸런싱이 완료되었습니다.',
            },
            _MODES.rebalancing: {
                _STATUS.on_hold: '리밸런싱이 발생했습니다.',
                _STATUS.processing: '리밸런싱 신청이 성공적으로 완료되었습니다.',
                _STATUS.completed: '리밸런싱이 완료되었습니다.',
                _STATUS.skipped: '리밸런싱이 완료되었습니다.',
            },
        }
    }

    TYPE_MESSAGES = {
        'PA': {
            'sms': {
                _MODES.new_order: {
                    _STATUS.processing: '연금 자문 계약 및 설정이 성공적으로 완료되었습니다.\n'
                                        '원활한 연금 투자를 위해 연금계좌에 초기 투자금액 입금 및 자동이체를 꼭 설정하세요.\n'
                                        '투자금 입금 후 영업일 기준 익일 오전 포트폴리오 매수가 진행됩니다.\n'
                                        '* 정확한 계좌정보는 앱내 [전체 > 내 계약정보]에서 확인 가능합니다.'
                }
            },
            'push': {
                _MODES.new_order: {
                    _STATUS.processing: '연금 자문 계약 및 설정이 성공적으로 완료되었습니다.\n'
                                        '원활한 연금 투자를 위해 연금계좌에 초기 투자금액 입금 및 자동이체를 꼭 설정하세요.\n'
                                        '투자금 입금 후 영업일 기준 익일 오전 포트폴리오 매수가 진행됩니다.'
                }
            },
            'app': {
                _MODES.new_order: {
                    _STATUS.processing: '연금 자문 계약 및 설정이 성공적으로 완료되었습니다.\n'
                                        '원활한 연금 투자를 위해 연금계좌에 초기 투자금액 입금 및 자동이체를 꼭 설정하세요.\n'
                                        '투자금 입금 후 영업일 기준 익일 오전 포트폴리오 매수가 진행됩니다.'
                }
            }
        }
    }


class OrderDetailChoices:
    TYPE = Choices((1, 'buy', '매수'),
                   (2, 'sell', '환매'))

    RESULT = Choices((1, 'success', '성공'),
                     (2, 'failed', '실패'),
                     (3, 'canceled', '취소됨'),
                     (4, 'on_hold', '대기중'))