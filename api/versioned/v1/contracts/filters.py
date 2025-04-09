from api.bases.contracts.models import Contract
from django_filters.constants import STRICTNESS
from common import filters


class AccountHistoryFilter(filters.FilterSet):
    start_date = filters.FakeDateTimeFilter(input_formats=['%Y-%m-%d'], required=True, help_text='시작일(YYYY-MM-DD)')
    end_date = filters.FakeDateTimeFilter(input_formats=['%Y-%m-%d'], required=True, help_text='종료일(YYYY-MM-DD)')
    repeat_key = filters.FakeCharFilter(help_text='연속조회키', required=False, empty_value=None)
    ordering = filters.FakeCharFilter(required=False, empty_value=None, help_text='정렬기준구분코드(A: 오름차순, D: 내림차순, 기본값: D)')

    class Meta:
        model = Contract
        fields = ['start_date', 'end_date', 'repeat_key', 'ordering']
        strict = STRICTNESS.RAISE_VALIDATION_ERROR


class CardAmountFilter(filters.FilterSet):
    start_date = filters.FakeDateTimeFilter(input_formats=['%Y-%m-%d'], required=True, help_text='시작일(YYYY-MM-DD)')

    class Meta:
        model = Contract
        fields = ['start_date']
        strict = STRICTNESS.RAISE_VALIDATION_ERROR


class SettlementFilter(filters.FilterSet):
    type = filters.FakeChoiceFilter(required=False, null_value=None,
                                    choices=(('yearly_performance_fee', '[연수취] 성과보수'),
                                             ('yearly_cancelation_fee', '[연수취] 해지정산'),
                                             ('monthly_periodic_fee', '[월수취] 정기수수료'),
                                             ('monthly_cancelation_fee', '[월수취] 해지정산')),
                                    help_text='정산 타입')

    class Meta:
        model = Contract
        fields = ['type']
        strict = STRICTNESS.RAISE_VALIDATION_ERROR
