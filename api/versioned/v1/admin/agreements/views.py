from rest_framework import viewsets, filters
from common.viewsets import AdminViewSetMixin, CreateListMixin
from api.bases.agreements.models import Type, Agreement
from api.versioned.v1.admin.agreements.serializers import TypeSerializer, AgreementSerializer


class TypeViewSet(AdminViewSetMixin,
                  viewsets.ModelViewSet):
    """
    create: [동의 타입 생성]
    동의 타입을 생성합니다.

    list: [동의 타입 목록 조회]
    정의된 동의 타입 전체 목록을 조회합니다.

    retrieve: [동의 타입 상세 조회]
    update: [동의 타입 업데이트]
    partial_update: [동의 타입 부분 업데이트]
    destroy: [동의 타입 삭제]
    """
    queryset = Type.objects.all()
    serializer_class = TypeSerializer


class AgreementViewSet(AdminViewSetMixin,
                       CreateListMixin,
                       viewsets.ModelViewSet):
    """
    create: [동의 처리]
    유저의 미동의한 항목에 대한 동의 처리합니다.</br>
    리스트 형태로 요청하면 한번에 여러건 처리됩니다.</br>
    ---
    여러건 동시 요청 예시
    ```javascript
    [
        {"type": "type1", "user": "uuid"},
        {"type": "type2", "user": "uuid"}
    ]
    ```

    list: [동의 목록 조회]
    유저들이 동의한 목록을 조회합니다.</br>
    타입, 유저 이메일, 유저이름 기준으로 검색 가능합니다.</br>

    retrieve: [동의 상세 조회]
    update: [동의 업데이트]
    partial_update: [동의 부분 업데이트]
    destroy: [동의 삭제]
    """

    queryset = Agreement.objects.all()
    serializer_class = AgreementSerializer
    filter_backends = (filters.OrderingFilter, filters.SearchFilter,)
    search_fields = ('=type__id', 'user__email', 'user__profile__name')
    lookup_value_regex = '[0-9a-f-]+'
