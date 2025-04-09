from reversion.admin import VersionAdmin

from django.conf import settings
from django.core.cache import caches
from django.contrib import admin
from django.http import HttpResponseRedirect

from .models import Account, Asset, AssetDetail

from api.bases.orders.models import Event
from api.bases.accounts.services.rebalancing_simulation import (
    AccountRebalancingSimulationService,
)
from api.bases.managements.components.order_account import OrderRequester


TR_BACKEND = settings.TR_BACKEND


class AccountNumberSearchMixin(object):
    search_fields = ("account_alias__in",)

    def get_account_pk(self, search_term):
        accounts = []
        for item in Account.objects.iterator():
            if str(search_term) in str(item.account_number):
                accounts.append(str(item.pk))

        return accounts

    def get_search_results(self, request, queryset, search_term):
        search_fields = self.get_search_fields(request)
        if not search_term:
            return queryset, False
        accounts = self.get_account_pk(search_term)
        for field in search_fields:
            queryset = queryset.filter(**{field: accounts})
        return queryset, False


class AssetTabularInline(admin.TabularInline):
    model = Asset
    ordering = ["-created_at"]
    can_delete = False
    extra = 0
    readonly_fields = [
        "base",
        "deposit",
        "balance",
        "prev_deposit",
        "base_usd",
        "deposit_usd",
        "balance_usd",
        "created_at",
    ]


class OrderTabularInline(admin.TabularInline):
    model = Event
    ordering = ["-created_at"]
    can_delete = False
    extra = 0
    readonly_fields = ["portfolio_id", "mode", "status", "created_at", "completed_at"]


@admin.register(Account)
class AccountAdmin(AccountNumberSearchMixin, VersionAdmin):
    change_form_template = "admin/account_change_form.html"
    list_display = (
        "account_number",
        "account_alias",
        "vendor_code",
        "account_type",
        "status",
        "risk_type",
        "strategy_code",
        "created_at",
        "updated_at",
        "deleted_at",
    )
    list_filter = (
        "vendor_code",
        "account_type",
        "status",
        "risk_type",
        "strategy_code",
        "created_at",
        "updated_at",
        "deleted_at",
    )

    inlines = [OrderTabularInline, AssetTabularInline]
    history_latest_first = True

    def reversion_register(self, model, **options):
        options["exclude"] = ("account_number",)
        super().reversion_register(model, **options)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        account_status = self._get_account_status(object_id)
        extra_context["account_status_exists"] = False
        if account_status is not None:
            try:
                extra_context.update(
                    self._get_extra_context_from_account_status(account_status)
                )
            except KeyError:
                extra_context["account_status_exists"] = False
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )

    def save_model(self, request, obj, form, change):
        if "_simulate_rebalancing" in request.POST:
            return
        return super().save_model(request, obj, form, change)

    def response_change(self, request, obj):
        if "_simulate_rebalancing" in request.POST:
            api_base = TR_BACKEND[str(obj.vendor_code).upper()].HOST
            requester = OrderRequester(api_base, obj.vendor_code)
            service = AccountRebalancingSimulationService(obj, requester)
            service.refresh()
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    def _get_account_status(self, account_alias):
        return caches["account_status"].get(f"{account_alias}")

    def _get_extra_context_from_account_status(self, account_status):
        extra_context = dict(
            account_status_exists=True,
            account_status_is_succeeded=account_status["is_succeeded"],
            account_status_executed_at=account_status["executed_at"],
        )
        if account_status["is_succeeded"]:
            _extra_context = dict(
                account_status_rebalancing_simulation_report=account_status[
                    "rebalancing_simulation_report"
                ],
                account_status_base=account_status["base"],
                account_status_all_shares_value=account_status["all_shares_value"],
                account_status_min_deposit_to_rebalance_lower=account_status[
                    "min_deposit_to_rebalance"
                ]["lower"],
                account_status_min_deposit_to_rebalance_base=account_status[
                    "min_deposit_to_rebalance"
                ]["base"],
                account_status_min_deposit_to_rebalance_upper=account_status[
                    "min_deposit_to_rebalance"
                ]["upper"],
                account_status_required_base_margin_to_rebalance=AccountRebalancingSimulationService.REQUIRED_BASE_MARGIN_TO_REBALANCE,
            )
        else:
            _extra_context = dict(
                account_status_error=account_status["error"],
            )
        extra_context.update(_extra_context)
        return extra_context


class AssetAdmin(AccountNumberSearchMixin, admin.ModelAdmin):
    list_display = (
        "account_alias_id",
        "base",
        "deposit",
        "balance",
        "prev_deposit",
        "base_usd",
        "deposit_usd",
        "balance_usd",
        "created_at",
        "updated_at",
    )
    list_filter = ("created_at", "updated_at")


class AssetDetailAdmin(AccountNumberSearchMixin, admin.ModelAdmin):
    list_display = (
        "account_alias_id",
        "code",
        "shares",
        "buy_price",
        "balance",
        "buy_price_usd",
        "balance_usd",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "code",
        "created_at",
        "updated_at",
    )


admin.site.register(Asset, AssetAdmin)
admin.site.register(AssetDetail, AssetDetailAdmin)
