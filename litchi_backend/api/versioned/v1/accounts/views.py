from rest_framework import viewsets
from rest_framework.response import Response

from api.bases.contracts.adapters import account_adapter

from .serializers import AccountRetrieveSerializer


class AccountViewSet(viewsets.ReadOnlyModelViewSet):
    """
    retrieve: Account 조회

    """
    serializer_class = AccountRetrieveSerializer
    lookup_field = 'account_alias'

    def retrieve(self, request, *args, **kwargs):
        resp = account_adapter.request(f'/api/v1/accounts/{self.kwargs[self.lookup_field]}', method='GET')
        try:
            resp.raise_for_status()
        except Exception as e:
            return Response(status=resp.status_code, data=resp.json())

        serializer = self.get_serializer(resp.json())
        return Response(status=resp.status_code, data=serializer.data)
