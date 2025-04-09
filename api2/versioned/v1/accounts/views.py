from rest_framework import viewsets

from api.bases.accounts.models import Account
from .serializers import AccountSerializer
from .filters import AccountFilter


class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    """
    retrieve:계좌 조회

    해당 account_alias의 계좌를 조회합니다.
    ---

    list:계좌 목록 조회

    계좌 목록을 조회합니다.
    ---

    """

    serializer_class = AccountSerializer
    queryset = Account.objects.all()
    filter_class = AccountFilter
