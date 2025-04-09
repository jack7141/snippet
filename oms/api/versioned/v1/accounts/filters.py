from django_filters import rest_framework as filters
from api.bases.accounts.models import Account
from common.utils import gen_choice_desc


class AccountFilter(filters.FilterSet):
    status = filters.ChoiceFilter(
        field_name="status",
        choices=Account.STATUS,
        help_text=gen_choice_desc("계좌 상태", Account.STATUS),
    )
    type = filters.ChoiceFilter(
        field_name="account_type",
        choices=Account.ACCOUNT_TYPE,
        help_text=gen_choice_desc("자산 구분", Account.ACCOUNT_TYPE),
    )
    order_setting_name = filters.CharFilter(
        field_name="order_setting", lookup_expr="name", help_text="주문 설정(기본값: default)"
    )
