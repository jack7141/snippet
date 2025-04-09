from model_utils import Choices


class ScoreRangeChoices:
    RISK_TYPES = Choices(('0', 'lowest', '안정형'),
                         ('1', 'low', '안정추구형'),
                         ('2', 'medium', '중립형'),
                         ('3', 'high', '성장형'),
                         ('4', 'highest', '공격형'))


class QuestionChoices:
    QUESTION_TYPES = Choices('select', 'multiple_select')

    SEPARATOR_TYPES = Choices((',', 'comma', '쉼표'),
                              ('.', 'period', '마침표'),
                              ('|', 'pipe', '분리선'),
                              (':', 'colon', '쌍점'))


class ResponseChoices:
    AUTH_TYPES = Choices(('Biometric', [(10, 'biometric', '바이오인증'),
                                        (11, 'fingerprint', '지문'),
                                        (12, 'face', '얼굴'),
                                        (13, 'iris', '홍채')]),
                         ('Ownership', [(20, 'ownership', '소유주인증'),
                                        (21, 'sms', 'SMS'),
                                        (22, 'otp', 'OTP'),
                                        (23, 'security_card', '보안카드')]),
                         ('Knowledge', [(30, 'knowledge', '지식기반인증'),
                                        (31, 'password', '패스워드'),
                                        (32, 'pattern', '패턴'),
                                        (33, 'pin', 'PIN')
                                        ]))
