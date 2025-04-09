from model_utils import Choices


class ContractChoices:
    ORDER_STATUS = Choices((1, 'pending', '지연중'),
                           (2, 'failed', '실패'),
                           (3, 'on_hold', '대기중'),
                           (4, 'processing', '진행중'),
                           (5, 'completed', '완료됨'),
                           (6, 'canceled', '취소됨'),
                           (7, 'skipped', '건너뜀'))

    ORDER_MODES = Choices(('new_order', '신규'),
                          ('sell', '리밸런싱-매도'),
                          ('buy', '리밸런싱-매수'),
                          ('rebalancing', '리밸런싱'),
                          ('total_sell', '전체매도'))

    STATUS = Choices((0, 'canceled', '해지됨'),
                     (1, 'normal', '정상 유지'),
                     ('Vendor', [(4, 'vendor_wait_cancel', '협력사 해지 대기'),
                                 (41, 'vendor_wait_account', '협력사 계좌개설 대기')])
                     )


class ContractTypeChoices:
    FEE_PERIOD = Choices(
        (1, 'yearly'),
        (2, 'monthly'),
        (3, 'quarterly')
    )

    OPERATION_TYPE = Choices(('A', '자문',),
                             ('D', '일임'))

    ASSET_TYPE = Choices(('kr_fund', '국내 펀드'),
                         ('kr_etf', '국내 ETF'),
                         ('etf', '해외 ETF'))

    FEE_TYPE = Choices((1, 'pre', '선취'),
                       (2, 'post', '후취'),
                       (3, 'per', '건당 결제'),
                       (4, 'free', '무료'))

    DATE_METHOD = Choices((1, 'default', '일 기준'),
                          (2, 'business', '영업일 기준'))


class TermDetailChoices:
    MIN_MAX = Choices(
        (1, 'Min'),
        (2, 'Max'),
        (3, None)
    )
    PERIOD_TYPE = Choices(
        (1, 'days'),
        (2, 'weeks'),
        (3, 'months'),
        (4, 'years')
    )


class ConditionChoices:
    REG_DATE = Choices((1, '매월 1일'),
                       (5, '매월 5일'),
                       (10, '매월 10일'),
                       (15, '매월 15일'),
                       (20, '매월 20일'),
                       (25, '매월 25일'))


class RebalancingQueueChoices:
    STATUS = Choices((1, 'pending', '지연중'),
                     (2, 'failed', '실패'),
                     (3, 'on_hold', '대기중'),
                     (4, 'processing', '진행중'),
                     (5, 'completed', '완료됨'),
                     (6, 'canceled', '취소됨'),
                     (7, 'skipped', '건너뜀'))


class ProvisionalContractChoices:
    ACCOUNT_OPEN_STEP_STATUS = Choices(
        ('Intro', [
            ('account_open', '비대면 계좌개설 진행'),
            ('account_multi_status', '비대면 단기다수 계좌')]),
        ('Information', [
            ('new_user_progress', '신규 회원'),
            ('old_user_progress', '기존 회원'),
            ('user_completed', '정보 입력')]),
        ('Identification', [
            ('third_party_agreement', '제3자 정보제공 동의'),
            ('ocr_initial', '신분증 진위 확인'),
            ('ocr_checked', '신분증 확인 요청'),
            ('ocr_confirm', '신분증 확인 완료'),
            ('personal_info', '개인 정보 입력'),
            ('address_search', '주소 검색'),
            ('address_search_result', '주소 검색 결과'),
            ('address_search_detail', '상세 주소 입력'),
        ]),
        ('Account', [
            ('password_initial', '비밀번호 입력'),
            ('password_confirm', '비밀번호 확인')]),
        ('Authorization', [
            ('sender_initial', '역 이체 인증 진입'),
            ('sender_bank_number', '역 이체 인증 은행 선택'),
            ('sender_acct_number', '역 이체 인증 계좌 입력'),
            ('sender_post_message', '역 이체 인증 1원 송금')]),
        ('Completed', [
            ('account_processing', '계좌개설 진행'),
            ('account_completed', '계좌개설 완료')]))


class ReservedActionChoices:
    STATUS = Choices(('reserved', '예약'),
                     ('reserve_failed', "예약 실패"),
                     ('processing', '진행중'),
                     ('success', '성공'),
                     ('canceled', '취소'),
                     ('condition_failed', '사전 조건 실패'),
                     ('failed', '실패'))
    ACTIONS = Choices(('rebalancing', '리밸런싱 발생'), )


class TransferChoices:
    PRODUCT_TYPE = Choices(('Pension', [('1', 'irp', 'IRP'),
                                        ('2', 'saving', '연금저축')]), )

    STATUS = Choices((0, 'canceled', '해지됨'),
                     ('Pension', [(10, 'transfer_in_progress', '이체신청'),
                                  (11, 'transfer_check', '가입확인'),
                                  (12, 'transfer_ready', '이체예정'),
                                  (13, 'transfer_submit', '이체접수'),
                                  (14, 'transfer_done', '이체납입명세'),
                                  (15, 'transfer_fail', '이체실패'),
                                  (16, 'transfer_auto_fail', '자동취소')]))


class AccountStatusChoices:
    ACCOUNT_STATUS = Choices(('skiped', '실패',),
                             ('completed', '성공'))
