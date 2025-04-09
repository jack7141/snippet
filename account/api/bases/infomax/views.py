from rest_framework.mixins import ListModelMixin
from rest_framework.viewsets import GenericViewSet

from .models import Master, ClosingPrice
from .serializers import MasterSerializer, ClosingPriceSerializer


class MasterViewSet(ListModelMixin, GenericViewSet):
    serializer_class = MasterSerializer
    queryset = Master.objects.all()


class ClosingPriceViewSet(ListModelMixin, GenericViewSet):
    serializer_class = ClosingPriceSerializer
    queryset = ClosingPrice.objects.all().order_by('-timestamp')
