from django.contrib import admin
from .models import Auth  # Integrate


@admin.register(Auth)
class AuthenticationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'cert_type', 'code', 'is_verified', 'is_expired')
    search_fields = ('user__email', 'user__profile__name', 'user__profile__phone')
