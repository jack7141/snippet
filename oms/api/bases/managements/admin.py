from django.contrib import admin

from api.bases.accounts.admin import AccountNumberSearchMixin
from api.bases.managements.models import (
    Queue,
    OrderLog,
    OrderReport,
    ErrorSet,
    ErrorOccur,
    ErrorSolved,
)


# Register your models here.
class OrderLogTabularInline(admin.TabularInline):
    model = OrderLog
    ordering = ["-created"]
    can_delete = False
    extra = 0
    readonly_fields = [
        "order_id",
        "type",
        "status",
        "code",
        "shares",
        "error_msg",
        "created",
        "concluded_at",
        "modified",
    ]


class OrderReportTabularInline(admin.TabularInline):
    model = OrderReport
    ordering = ["-created"]
    can_delete = False
    extra = 0
    readonly_fields = ["order_id", "report_type", "title", "body", "config"]


@admin.register(Queue)
class OrderQueueAdmin(AccountNumberSearchMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "account_alias",
        "portfolio_id",
        "mode",
        "status",
        "note",
        "created",
        "modified",
    ]
    list_filter = ("status", "mode", "vendor_code")

    inlines = [OrderLogTabularInline, OrderReportTabularInline]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ("order_basket", "created", "modified", "management_at")
        return self.readonly_fields + ('account_alias',)


@admin.register(OrderLog)
class OrderLogAdmin(AccountNumberSearchMixin, admin.ModelAdmin):
    list_display = [
        "order_id",
        "account",
        "account_alias",
        "type",
        "status",
        "code",
        "shares",
        "error_msg",
        "created",
        "concluded_at",
        "modified",
    ]
    list_filter = ("status", "type")
    search_fields = ("order__account_alias__in",)
    readonly_fields = ("order",)


@admin.register(OrderReport)
class OrderReportAdmin(admin.ModelAdmin):
    list_display = ["order_id", "report_type", "title", "body", "config"]
    list_filter = ("report_type",)
    readonly_fields = ("order",)


@admin.register(ErrorSet)
class ErrorSetAdmin(admin.ModelAdmin):
    list_display = ["error_msg", "response_manual"]


@admin.register(ErrorSolved)
class ErrorSolvedAdmin(admin.ModelAdmin):
    list_display = ["error_occur_id", "solved_at"]


#     # list_filter = ('report_type',)


@admin.register(ErrorOccur)
class ErrorOccurAdmin(admin.ModelAdmin):
    search_fields = ("account_alias",)
    ordering = ["-occured_at"]
    # readonly_fields = ['error','order','account_alias', 'get_error_msg', 'occured_at', 'get_solved_at', 'get_response_manual', 'get_order_note']
    readonly_fields = [
        "order",
        "account_alias",
        "get_error_msg",
        "occured_at",
        "get_solved_at",
        "get_response_manual",
        "get_order_note",
    ]

    def get_solved_at(self, obj):
        return obj.errorsolved.solved_at

    get_solved_at.short_description = "solved_at"
    get_solved_at.admin_order_field = "errorsolved__solved_at"

    def get_response_manual(self, obj):
        return obj.error.response_manual

    get_response_manual.short_description = "response_manual"

    def get_error_msg(self, obj):
        return obj.error.error_msg

    get_error_msg.short_description = "error_msg"
    get_error_msg.admin_order_field = "error__error_msg"

    def get_order_note(self, obj):
        if obj.order == None:
            return None
        else:
            return obj.order.note

    get_order_note.short_description = "order_note"

    list_display = [
        "account_alias",
        "get_error_msg",
        "occured_at",
        "get_solved_at",
        "get_response_manual",
        "get_order_note",
    ]
    list_filter = ("error__error_msg",)
