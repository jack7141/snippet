from rest_framework import viewsets, filters, mixins
from common.viewsets import CreateListMixin
from common.exceptions import PreconditionRequired
from api.bases.agreements.models import Type, Agreement, AgreementGroup
from api.versioned.v1.agreements.serializers import TypeSerializer, AgreementSerializer, AgreementGroupSerializer


class TypeViewSet(mixins.ListModelMixin,
                  viewsets.GenericViewSet):
    """
    list: [동의 목록 조회]
    동의 가능한 항목을 조회합니다.
    """
    queryset = Type.objects.all().order_by('-created_at')
    serializer_class = TypeSerializer


class AgreementGroupViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list: [계약 조건 목록 조회]
    publish 된 계약 목록을 조회합니다. 목록 조회시 기본값으로 적용되어있는 조건을 필터링 할 수 있습니다.

    retrieve: [계약 조건 상세 조회]
    """
    queryset = AgreementGroup.objects.filter(is_publish=True, is_default=True)
    serializer_class = AgreementGroupSerializer
    filter_fields = ('title',)


class AgreementViewSet(CreateListMixin,
                       viewsets.ModelViewSet):
    """
    create: [동의 처리]
    미동의한 항목에 대한 동의 처리합니다.</br>
    리스트 형태로 요청하면 한번에 여러건 처리됩니다.</br>

    ---
    여러건 동시 요청 예시
    ```javascript
    [
        {"type": "type code"},
        {"type": "type code"}
    ]
    ```

    list: [동의 완료 목록 조회]
    현재까지 동의한 목록을 조회합니다.
    타입 기준으로 검색 가능합니다. </br>

    delete: [동의 취소]
    현재 동의한 항목중 동의 타입의 is_required가 false인 경우(선택적 동의) 동의를 취소 할 수 있습니다.</br>
    동의 필수인 항목을 취소 시도하는 경우 428 status code를 받습니다.
    """

    queryset = Agreement.objects.all().order_by('-created_at')
    serializer_class = AgreementSerializer

    filter_backends = (filters.OrderingFilter, filters.SearchFilter,)
    search_fields = ('=type__id',)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_destroy(self, instance):
        if not instance.type.is_required:
            instance.delete()
        else:
            raise PreconditionRequired('this agreement is not optional type.')
