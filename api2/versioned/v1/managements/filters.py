import pytz
from datetime import datetime, timedelta
from django_filters import rest_framework as filters
from api.bases.managements.models import Queue, OrderLog, ErrorSet
from common.utils import gen_choice_desc


class DateFilter(filters.Filter):
    def filter(self, qs, value):
        if value:
            target_dt = self.parse_dt(value=value)
            kwargs = {
                f"{self.field_name}__year": target_dt.year,
                f"{self.field_name}__month": target_dt.month,
                f"{self.field_name}__day": target_dt.day,
            }
            return qs.filter(**kwargs)
        return qs

    def parse_dt(self, value):
        target_dt = datetime.strptime(value, "%Y%m%d")
        return target_dt


class ErrorOccurFilter(filters.FilterSet):

    error_ids = filters.CharFilter(
        help_text=gen_choice_desc(
            "Default-전체 Or Comma_Separated \n", ErrorSet.ERROR_CODE
        ),
        method="error_ids_split",
    )
    account_alias = filters.CharFilter(
        help_text="Default-전체 Or Comma_Separated", method="account_alias_split"
    )
    is_error_alive = filters.BooleanFilter(
        help_text="Default-전체 Or Boolean",
        field_name="errorsolved__solved_at",
        lookup_expr="isnull",
    )

    def error_ids_split(self, queryset, name, value):
        error_ids = value.split(",")
        queryset = queryset.filter(error_id__in=error_ids)
        return queryset

    def account_alias_split(self, queryset, name, value):
        account_alias = value.split(",")
        queryset = queryset.filter(account_alias__in=account_alias)
        return queryset


class OrderQueueFilter(filters.FilterSet):
    mode = filters.ChoiceFilter(
        field_name="mode",
        help_text=gen_choice_desc("Queue 모드", Queue.MODES),
        choices=Queue.MODES,
    )
    status = filters.ChoiceFilter(
        field_name="status",
        help_text=gen_choice_desc("Queue 상태", Queue.STATUS),
        choices=Queue.STATUS,
    )
    created = DateFilter(field_name="created", help_text="생성일자(YYYYMMDD), KST 기준")
    portfolio_id = filters.NumberFilter(field_name="portfolio_id", help_text="포트폴리오 ID")


class OrderLogFilter(filters.FilterSet):
    type = filters.ChoiceFilter(
        field_name="type",
        choices=OrderLog.TYPE,
        help_text=gen_choice_desc("주문 로그 종류", OrderLog.TYPE),
    )
    status = filters.ChoiceFilter(
        field_name="status",
        choices=OrderLog.STATUS,
        help_text=gen_choice_desc("주문 로그 상태", OrderLog.STATUS),
    )
    created = DateFilter(field_name="created", help_text="생성일자(YYYYMMDD), KST 기준")

    class Meta:
        fields = ["type", "status", "created"]
