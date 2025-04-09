from django.utils.translation import ugettext_lazy as _
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from .models import User, Profile, ExpiringToken


class UserProfileInline(admin.StackedInline):
    model = Profile


class UserExpiringTokenInline(admin.StackedInline):
    can_delete = False
    show_change_link = True
    model = ExpiringToken


@admin.register(User)
class UserAdmin(UserAdmin):
    model = User

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )

    list_filter = ("is_staff", "is_active", "groups", "date_joined")
    list_display = ("email", "name", "is_staff", "date_joined")
    search_fields = ("email", "profile__name", "profile__phone")
    ordering = ("email",)
    inlines = [
        UserProfileInline,
    ]

    def name(self, instance):
        return instance.profile.name

    name.admin_order_field = "profile__name"


@admin.register(ExpiringToken)
class ExpiringTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "key", "created", "updated", "is_expired")
    actions = ("expire_token",)
    search_fields = ("user__email",)
    fields = ("user",)

    def is_expired(self, instance):
        return instance.expired()

    def expire_token(self, request, instance):
        instance.update(updated=timezone.now() - timezone.timedelta(days=1))

    is_expired.boolean = True
    expire_token.short_description = "Expire selected Tokens"
