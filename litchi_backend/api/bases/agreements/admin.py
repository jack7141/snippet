from django.contrib import admin, messages

from api.bases.agreements.models import Type, Agreement, AgreementGroup


@admin.register(Type)
class TypeAdmin(admin.ModelAdmin):
    list_display = ('agreement_group', 'code', 'name', 'created_at', 'updated_at')
    list_filter = ('agreement_group', 'created_at')
    search_fields = ('agreement_group__title', 'code', 'name')


class TypeInlineAdmin(admin.TabularInline):
    model = Type
    extra = 0
    ordering = ('code',)


@admin.register(AgreementGroup)
class AgreementGroupAdmin(admin.ModelAdmin):
    inlines = (TypeInlineAdmin,)
    list_display = ('title', 'is_default', 'is_publish', 'created_at', 'updated_at')
    search_fields = ('title', 'is_default', 'is_publish')


@admin.register(Agreement)
class AgreementAdmin(admin.ModelAdmin):
    list_display = ('agreement_group', 'type', 'user', 'name', 'created_at')
    list_filter = ('agreement_group', 'type', 'created_at')
    search_fields = ('agreement_group__title', 'agreement_group__is_default', 'type__code', 'user__email')
    raw_id_fields = ('user',)

    def name(self, instance):
        return instance.user.profile.name
