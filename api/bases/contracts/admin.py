from django.conf import settings
from django.contrib import admin, messages
from django.utils import timezone

from api.bases.orders.models import Order
from api.bases.contracts.models import (
    Condition,
    Contract,
    ContractType,
    ContractStatus,
    Extra,
    ProvisionalContract,
    ReservedAction,
    Rebalancing,
    RebalancingQueue,
    Transfer,
    Term,
    TermDetail,
)
from api.bases.contracts.mixins import RebalancingMixin
from api.bases.notifications.choices import NotificationChoices
from api.versioned.v1.contracts.mixins import TerminateContractMixin


class OrderInline(admin.TabularInline):
    can_delete = settings.DEBUG
    model = Order
    extra = 0
    raw_id_fields = ('user', 'order_rep',)


class RebalancingInline(admin.TabularInline):
    can_delete = settings.DEBUG
    show_change_link = True
    model = Rebalancing
    extra = 0
    ordering = ('-created_at',)
    exclude = ('notifications',)
    readonly_fields = ('sold_at', 'bought_at', 'note', 'created_at')


class RebalancingQueueInline(admin.TabularInline):
    model = RebalancingQueue
    ordering = ('-created_at',)
    extra = 0
    readonly_fields = ('created_at', 'updated_at',)


class ConditionInline(admin.StackedInline):
    model = Condition


class ExtraInline(admin.StackedInline):
    model = Extra


class RebalancingFilter(admin.SimpleListFilter):
    title = 'Rebalancing Required'
    parameter_name = 'reb_required'

    def lookups(self, request, model_admin):
        return [(True, True), (False, False)]

    def queryset(self, request, queryset):
        if self.value() == 'True':
            return queryset.filter(id__in=[item.id for item in queryset if item.reb_required])
        elif self.value() == 'False':
            return queryset.exclude(id__in=[item.id for item in queryset if item.reb_required])
        else:
            return queryset


class OrderModeFilter(admin.SimpleListFilter):
    title = 'Last Order Mode'
    parameter_name = 'last_order_mode'

    def lookups(self, request, model_admin):
        return Order.MODES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                id__in=[item.id for item in queryset if item.last_order and item.last_order.mode == self.value()])

        return queryset


class OrderStatusFilter(admin.SimpleListFilter):
    title = 'Last Order Status'
    parameter_name = 'last_order_status'

    def lookups(self, request, model_admin):
        return Order.STATUS

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                id__in=[item.id for item in queryset if
                        item.last_order and item.last_order.status == int(self.value())])

        return queryset


@admin.register(ContractType)
class ContractTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(ContractStatus)
class ContractStatusAdmin(admin.ModelAdmin):
    list_display = ('category', 'code', 'type', 'name')
    list_filter = ('category',)


@admin.register(Contract)
class ContractAdmin(TerminateContractMixin,
                    RebalancingMixin,
                    admin.ModelAdmin):
    list_display = ('contract_number', 'user', 'name', 'contract_type', 'created_at', 'is_canceled',
                    'status', 'canceled_at', 'rebalancing', 'reb_required', 'term_detail')
    list_filter = ('contract_type', 'created_at', 'is_canceled', 'rebalancing', 'term_detail',
                   RebalancingFilter, OrderModeFilter, OrderStatusFilter)
    search_fields = ('user__email', 'user__profile__name', 'user__profile__phone', 'contract_type__code',)
    actions = ['rebalancing', 'cancel_contract']
    inlines = [ConditionInline, ExtraInline, OrderInline, RebalancingInline, RebalancingQueueInline]
    readonly_fields = ('created_at',
                       'updated_at',
                       'canceled_at',
                       'next_rebalancing',
                       'firm_agreement_at',
                       'acct_completed_at')
    raw_id_fields = ('user', 'vendor', 'term',)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.assets.exists():
            return ('account_alias',) + self.readonly_fields
        return self.readonly_fields

    def name(self, instance):
        return instance.user.profile.name

    name.admin_order_field = "user__profile__name"

    def reb_required(self, instance):
        return instance.reb_required

    reb_required.boolean = True

    def rebalancing(self, request, queryset):
        reb_targets = queryset.filter(is_canceled=False)
        ret = []

        for target in reb_targets:
            if not target.last_order or target.last_order.status not in [Order.STATUS.completed,
                                                                         Order.STATUS.canceled,
                                                                         Order.STATUS.failed,
                                                                         Order.STATUS.skipped]:
                self.message_user(request, '%s item does not meet conditions.' % str(target), messages.ERROR)
                continue

            self.rebalancing_instance(target, force_send=True)
            ret.append(target)

        if len(ret) > 0:
            count = 'item' if len(ret) == 1 else 'items'
            self.message_user(request, '%s %s successfully rebalancing. (%s)' %
                              (len(ret), count, ','.join([str(item) for item in reb_targets])))

    def cancel_contract(self, request, queryset):
        for query in queryset:
            try:
                self.perform_destroy(query)
            except Exception as e:
                self.message_user(request, '{} - {}'.format(query.contract_number, e.detail), messages.ERROR)
            else:
                self.message_user(request, '{} - successfully canceled.'.format(query.contract_number))

    rebalancing.short_description = 'Rebalancing selected contracts'
    cancel_contract.short_description = 'Cancel selected contracts'


@admin.register(ProvisionalContract)
class ProvisionAdmin(admin.ModelAdmin):
    list_display = ('account_alias', 'name', 'contract_type', 'user', 'step', 'is_contract', 'created_at', 'updated_at')
    list_filter = ('contract_type', 'is_contract', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__profile__name', 'user__profile__phone')
    raw_id_fields = ('contract', 'user',)

    def name(self, instance):
        return instance.user.profile.name

    name.admin_order_field = "user__profile__name"


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at', 'is_default', 'is_publish', 'contract_type')
    list_filter = ('is_publish', 'is_default', 'contract_type')


@admin.register(ReservedAction)
class ReservedActionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'action', 'start_at', 'register', 'status', 'created_at', 'updated_at')
    ordering = ('-updated_at',)
    raw_id_fields = ('contract',)

    def save_model(self, request, obj, form, change):
        obj.register = request.user
        obj.save()


@admin.register(Condition)
class ConditionAdmin(admin.ModelAdmin):
    raw_id_fields = ('contract',)


class NotificationInline(admin.TabularInline):
    can_delete = False
    model = Rebalancing.notifications.through
    extra = 0
    ordering = ('-notification__created_at',)
    fields = ('title', 'message', 'protocol', 'created_at')
    readonly_fields = ('title', 'message', 'protocol', 'created_at')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(notification__protocol=NotificationChoices.PROTOCOLS.sms)

    def title(self, instance):
        return instance.notification.title

    def message(self, instance):
        return instance.notification.message

    def protocol(self, instance):
        return instance.notification.get_protocol_display()

    def created_at(self, instance):
        return timezone.localtime(instance.notification.created_at).strftime('%Y-%m-%d %H:%M:%S %Z')


@admin.register(Rebalancing)
class RebalancingAdmin(admin.ModelAdmin):
    inlines = [NotificationInline, ]
    list_display = ('contract', 'sold_at', 'bought_at', 'created_at')
    list_filter = ('contract__contract_type',)
    search_fields = ('contract__user__email', 'contract__user__profile__name', 'contract__user__profile__phone',
                     'contract__contract_number')
    ordering = ('-created_at',)
    exclude = ('notifications',)
    readonly_fields = ('created_at',)
    raw_id_fields = ('contract',)


@admin.register(RebalancingQueue)
class RebalancingQueueAdmin(admin.ModelAdmin):
    list_display = ('contract', 'status', 'created_at', 'updated_at', 'completed_at')
    list_filter = ('contract__contract_type', 'created_at', 'completed_at', 'status')
    search_fields = ('contract__user__email', 'contract__user__profile__name', 'contract__user__profile__phone',
                     'contract__contract_number')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
    raw_id_fields = ('contract',)


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('contract', 'account_number', 'product_type', 'vendor', 'completed_at', 'is_canceled', 'canceled_at')
    list_filter = ('contract__contract_type',)
    search_fields = ('contract__user__email', 'contract__user__profile__name', 'contract__user__profile__phone',
                     'contract__contract_number')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'completed_at', 'canceled_at')
    raw_id_fields = ('contract',)


@admin.register(TermDetail)
class TermDetailAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'term', 'contract_type', 'version', 'amount', 'rate', 'min_max', 'effective_date', 'is_free', 'period_int',
        'period_type', 'is_default'
    )
    list_filter = ('min_max', 'is_free', 'term__contract_type', 'term__field_1')
    search_fields = ('term', 'contract__contract_number',)

    def contract_type(self, instance):
        return instance.term.contract_type

    def version(self, instance):
        return instance.term.field_1
