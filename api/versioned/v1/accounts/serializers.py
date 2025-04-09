from rest_framework import serializers


class AccountRetrieveSerializer(serializers.Serializer):
    account_type = serializers.CharField(source="accountType", max_length=8, allow_blank=True, help_text="자산 구분")
    account_alias = serializers.CharField(source="accountAlias", max_length=128, read_only=True,
                                          help_text="계좌번호 별칭(INDEX)")
    strategy_code = serializers.IntegerField(source="strategyCode", help_text="전략 구분")
    risk_type = serializers.IntegerField(source="riskType", allow_null=True, help_text="투자성향")
    status = serializers.IntegerField(help_text="계약 상태")
    vendor_code = serializers.CharField(source="vendorCode", max_length=8, help_text="증권사구분")
    created_at = serializers.DateTimeField(source="createdAt", help_text="생성일")
    updated_at = serializers.DateTimeField(source="updatedAt", help_text="수정일")
    deleted_at = serializers.DateTimeField(source="deletedAt", allow_null=True, help_text="삭제 요청 일자")

    class Meta:
        fields = ('account_type', 'account_alias', 'strategy_code', 'risk_type', 'status', 'vendor_code', 'created_at',
                  'updated_at', 'deleted_at')
