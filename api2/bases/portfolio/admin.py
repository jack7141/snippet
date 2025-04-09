from django.contrib import admin
from .models import Portfolio


# Register your models here.
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("port_seq", "port_date", "port_type", "bw_type", "update_date")
    list_filter = ("port_date", "bw_type")


admin.site.register(Portfolio, PortfolioAdmin)
