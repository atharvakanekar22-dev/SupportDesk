from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for the custom User model."""

    # Columns shown in the user list
    list_display = ("username", "email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")

    # Add the role field to the standard fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "SupportDesk Profile",
            {
                "fields": ("role", "phone", "department"),
            },
        ),
    )

    # Include role in the add-user form
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "SupportDesk Profile",
            {
                "fields": ("role", "phone", "department"),
            },
        ),
    )
