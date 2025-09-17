from django.contrib import admin
from .models import Client
from project_profiling.models import ProjectType


# manage_client/admin.py
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "company_name",
        "contact_name",
        "email",
        "phone",
        "client_type",
        "is_active",
        "project_count",
        "created_by",
        "created_at",
    )
    list_filter = ("client_type", "is_active", "created_at")
    search_fields = ("company_name", "contact_name", "email", "phone", "city", "state")
    readonly_fields = ("created_at", "updated_at", "full_address", "project_count")

    fieldsets = (
        ("Basic Information", {
            "fields": (
                "company_name",
                "contact_name",
                "email",
                "phone",
                "client_type",
                "is_active",
                "project_types",  # ✅ Added here
            )
        }),
        ("Address", {
            "fields": ("address", "city", "state", "zip_code", "full_address")
        }),
        ("Additional Info", {"fields": ("notes",)}),
        ("Audit", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def project_count(self, obj):
        return 0  # until projects are linked
    project_count.short_description = "Projects"

    def full_address(self, obj):
        return obj.get_full_address()
    full_address.short_description = "Full Address"
