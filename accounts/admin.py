"""
accounts/admin.py
────────────────────────────────────────────────────────────────
Registers the custom User model with Django's built-in admin site.

NOTE: This admin panel is a development convenience only. The
actual Admin-facing "Create User" / "Manage Users" screens will be
built later as custom WareFlow pages, not exposed through this
raw Django admin interface.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


class WareFlowUserAdmin(UserAdmin):
    """
    Extends Django's built-in UserAdmin so password hashing,
    permission handling, and the "change password" form keep
    working exactly as Django expects, while adding our own
    'role' field to the list and edit views.
    """

    # Columns shown in the user list page
    list_display = ("username", "email", "role", "is_active", "is_superuser")

    # Sidebar filters on the right of the list page
    list_filter = ("role", "is_active")

    # Adds the "role" field to the existing edit-user form sections,
    # right after the built-in personal info fields.
    fieldsets = UserAdmin.fieldsets + (
        ("WareFlow Role", {"fields": ("role",)}),
    )

    # Adds "role" to the "add new user" form as well
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("WareFlow Role", {"fields": ("role",)}),
    )


admin.site.register(User, WareFlowUserAdmin)