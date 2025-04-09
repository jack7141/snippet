from django.contrib import admin
from api.bases.orders.models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'mode', 'contract', 'contract_type', 'acct_alias', 'created_at', 'updated_at',
                    'completed_at', 'status', 'is_canceled')
    list_filter = ('mode', 'order_item__contract_type', 'created_at', 'completed_at', 'status',)
    ordering = ('-created_at', '-updated_at')
    search_fields = ('user__email', 'user__profile__name', 'user__profile__phone')
    raw_id_fields = ('user', 'order_item', 'order_rep',)

    def name(self, obj):
        if obj.user is not None:
            return obj.user.profile.name
        return None

    def contract(self, obj):
        if obj.order_item is not None:
            return obj.order_item.contract_number
        return None

    def contract_type(self, obj):
        if obj.order_item is not None:
            return obj.order_item.contract_type
        return None

    def acct_alias(self, obj):
        if obj.order_item is not None:
            return obj.order_item.account_alias
        return None

    def is_canceled(self, obj):
        if obj.order_item is not None:
            return obj.order_item.is_canceled
        return None

    contract.admin_order_field = 'order_item__contract_number'
    contract_type.admin_order_field = 'order_item__contract_type'
    acct_alias.admin_order_field = 'order_item__account_alias'
    name.admin_order_field = "user__profile__name"
    is_canceled.order_field = 'order_item__is_canceled'
    is_canceled.boolean = True
