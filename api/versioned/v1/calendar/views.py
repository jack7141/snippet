from rest_framework import viewsets
from rest_framework.response import Response

from api.bases.funds.models import *
from api.bases.funds.utils import BDay

from common.filter_backends import MappingDjangoFilterBackend
from common.viewsets import MappingViewSetMixin

from .serializers import (
    CalendarSerializer
)
from .filters import (
    CalendarFilter
)


class CalendarViewSet(MappingViewSetMixin,
                      viewsets.ModelViewSet):
    """
    list:[휴무일 목록조회]
    전체 목록 휴무일을 조회합니다.

    retrieve:[휴무일 조회]
    특정 날짜에 대한 휴무일을 조회합니다.

    holiday_interval:[영업일 계산 조회]
    입력한 현재날짜의 영업일을 더한 날짜를 계산합니다.
    """
    queryset = Calendar.objects.all().order_by('-date')
    serializer_class = CalendarSerializer

    filter_backends = (MappingDjangoFilterBackend,)
    filter_action_map = {
        'list': CalendarFilter,
    }

    def holiday_interval(self, request, days, *args, **kwargs):
        instance = self.get_object()
        calendar = Calendar.objects.get(date=(instance.date + BDay(int(days))))
        serializer = self.get_serializer(calendar)
        return Response(serializer.data)
