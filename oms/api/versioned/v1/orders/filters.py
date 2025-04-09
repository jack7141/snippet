from django_filters import rest_framework as filters
from api.bases.orders.models import Event
from common.utils import gen_choice_desc


class EventFilter(filters.FilterSet):
    status = filters.ChoiceFilter(
        field_name="status",
        choices=Event.STATUS,
        help_text=gen_choice_desc("Event 상태", Event.STATUS),
    )
    mode = filters.ChoiceFilter(
        field_name="mode",
        choices=Event.MODES,
        help_text=gen_choice_desc("자산 구분", Event.MODES),
    )
    portfolio_id = filters.NumberFilter(field_name="portfolio_id", help_text="포트폴리오 ID")
