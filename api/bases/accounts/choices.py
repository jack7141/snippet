from model_utils import Choices

ACCOUNT_TYPE = Choices(('kr_fund', '국내 펀드'),
                       ('kr_etf', '국내 ETF'),
                       ('etf', '해외 ETF'))

RISK_TYPE = Choices(
    (0, 'VERY_LOW', '초저위험'),
    (1, 'LOW', '저위험'),
    (2, 'MID', '중위험'),
    (3, 'HIGH', '고위험'),
    (4, 'VERY_HIGH', '초고위험'),
)

STATUS = Choices(
    (0, 'canceled', '해지됨'),
    (1, 'normal', '정상 유지'),
    (22, 'account_sell_reg', '해지 매도 진행 중'),
    (23, 'account_sell_f1', '해지 매도 실패'),
    (24, 'account_sell_s', '해지 매도 완료'),
    (25, 'account_exchange_reg', '환전 진행 중'),
    (26, 'account_exchange_f1', '환전 실패'),
    (27, 'account_exchange_s', '환전 완료'),
    ('suspension', [
        (3, 'account_suspension', '운용 중지'),
        (30, 'accident_suspension', '이상 계좌 중지'),
        (31, 'unsupported_suspension', '미지원 종목 보유 운용 중지'),
        (32, 'base_amount_suspension', '최소 원금 위반 중지'),
        (33, 'trade_suspension', '임의 거래 중지'),
        (34, 'risk_type_suspension', '투자 성향 안정형 운용 중지'),
    ])
)
