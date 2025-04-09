# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.admin import UserAdmin
from django.contrib import admin
from django.utils import timezone
from axes.admin import AccessLog, AccessAttempt, AccessLogAdmin, AccessAttemptAdmin
from auditlog.admin import LogEntryAdmin as _LogEntryAdmin, LogEntry

from .models import User, Profile, ExpiringToken, Tendency, VendorTendency, VendorProperty, SiteSettings, Image


class UserProfileInline(admin.StackedInline):
    model = Profile
    raw_id_fields = ('avatar',)
    can_delete = False


class TendencyInline(admin.StackedInline):
    model = Tendency
    can_delete = False

    readonly_fields = ('score',)

    def score(self, instance):
        try:
            return instance.get_score()
        except:
            return False


class VendorPropertyInline(admin.StackedInline):
    model = VendorProperty


class VendorTendencyInline(admin.StackedInline):
    model = VendorTendency
    fk_name = 'user'
    extra = 0
    raw_id_fields = ('vendor',)


class UserAdmin(UserAdmin):
    model = User
    readonly_fields = ('referral_code',)
    fieldsets = (
        (None, {'fields': ('email', 'password', 'referral_code')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_vendor',
                                       'groups', 'user_permissions', 'site')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'site'),
        }),
    )

    list_filter = ('is_staff', 'is_vendor', 'is_active', 'groups', 'date_joined', 'site')
    list_display = ('email', 'name', 'referral_code', 'is_staff', 'is_vendor', 'has_contract', 'is_ordered',
                    'date_joined', 'site')
    search_fields = ('id', 'email', 'profile__name', 'profile__phone')
    ordering = ('email',)
    inlines = [UserProfileInline, VendorPropertyInline, TendencyInline, VendorTendencyInline]

    def name(self, instance):
        return instance.profile.name

    def has_contract(self, instance):
        return instance.contract_set.filter(is_canceled=False).exists()

    def is_ordered(self, instance):
        return instance.orders.all().exists()

    name.admin_order_field = "profile__name"
    has_contract.boolean = True
    is_ordered.boolean = True


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'phone', 'birth_date', 'risk_type')
    search_fields = ('user__email', 'name', 'phone')
    raw_id_fields = ('user', 'avatar')


class ExpiringTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created', 'updated', 'is_expired')
    actions = ('expire_token',)
    search_fields = ('user__email',)
    fields = ('user',)
    raw_id_fields = ('user',)

    def is_expired(self, instance):
        return instance.expired()

    def expire_token(self, request, instance):
        instance.update(updated=timezone.now() - timezone.timedelta(days=1))

    is_expired.boolean = True
    expire_token.short_description = 'Expire selected Tokens'


class LogEntryAdmin(_LogEntryAdmin):
    search_fields = ['timestamp', 'object_repr', 'changes', 'actor__email', 'actor__profile__name']

    def created(self, obj):
        return timezone.localtime(obj.timestamp).strftime('%Y-%m-%d %H:%M:%S %Z')

    created.short_description = 'Created'


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site',)


@admin.register(Tendency)
class TendencyAdmin(admin.ModelAdmin):
    list_display = ('user',)
    search_fields = ('user__email', 'user__profile__name', 'user__profile__phone')


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    search_fields = ('file', 'avatar__name', 'avatar__user__email')
    list_display = ('id', 'file', 'width', 'height')


admin.site.register(User, UserAdmin)
admin.site.register(Profile, UserProfileAdmin)

admin.site.unregister(AccessLog)
admin.site.unregister(AccessAttempt)

admin.site.unregister(LogEntry)

AccessLogAdmin.date_hierarchy = None
AccessAttemptAdmin.date_hierarchy = None

admin.site.register(AccessLog, AccessLogAdmin)
admin.site.register(AccessAttempt, AccessAttemptAdmin)
admin.site.register(ExpiringToken, ExpiringTokenAdmin)
admin.site.register(LogEntry, LogEntryAdmin)
