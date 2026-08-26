"""
accounts/models.py
────────────────────────────────────────────────────────────────
Defines the custom User model for WareFlow.

WareFlow uses a SINGLE User model with a `role` field, rather than
separate Staff/Manager/Admin models or subclasses. Role determines
AUTHORIZATION only — it does not represent different data/behavior.

IMPORTANT: This file must exist and AUTH_USER_MODEL must be set in
settings.py BEFORE running the first migration.
"""

from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models


class User(AbstractUser):
    """
    Custom User model extending Django's built-in AbstractUser.

    AbstractUser already provides:
        - username
        - email          (we make this required + unique below)
        - password       (handled securely by Django's auth system)
        - first_name / last_name
        - is_active      (used by Admin to deactivate accounts without deleting them)
        - is_staff       (Django's own built-in flag for /admin/ access — NOT the same as our "STAFF" role)
        - is_superuser
        - date_joined

    We only ADD what WareFlow specifically needs: the `role` field.
    """

    class Role(models.TextChoices):
        """
        Defines the three WareFlow application roles.

        Using TextChoices instead of a plain tuple gives us:
            User.Role.STAFF   -> "STAFF"
            User.Role.MANAGER -> "MANAGER"
            User.Role.ADMIN   -> "ADMIN"
        which is safer than typing raw strings throughout the codebase.
        """
        STAFF = "STAFF", "Staff"
        MANAGER = "MANAGER", "Manager"
        ADMIN = "ADMIN", "Admin"

    # ── WareFlow-specific fields ─────────────────────────────────────────────

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STAFF,
        help_text="Determines what parts of WareFlow this user can access.",
    )

    # Email is required and unique for WareFlow (AbstractUser leaves it optional
    # and non-unique by default). This avoids two accounts sharing one email.
    email = models.EmailField(
        unique=True,
        blank=False,
        help_text="Used for account identification. Must be unique.",
    )

    # ── Convenience properties for role checks ───────────────────────────────
    # These make views/templates more readable than comparing raw strings,
    # e.g. "if request.user.is_manager:" instead of "if request.user.role == 'MANAGER':"

    @property
    def is_staff_role(self):
        """True if this user has the STAFF application role."""
        return self.role == self.Role.STAFF

    @property
    def is_manager(self):
        """True if this user has the MANAGER application role."""
        return self.role == self.Role.MANAGER

    @property
    def is_admin(self):
        """True if this user has the ADMIN application role."""
        return self.role == self.Role.ADMIN

    def __str__(self):
        # Shown in Django admin and shell — makes debugging easier
        return f"{self.username} ({self.get_role_display()})"


class Notification(models.Model):
    """
    Generic per-user notification. Deliberately has NO foreign key
    to StockAdjustmentRequest, Product, or any other business model
    — everything a notification needs to display and navigate is
    captured as plain text/URL fields at creation time. This keeps
    notifications fully independent of warehouse domain models, per
    the confirmed architecture boundary: a business record can be
    edited or reach a different state later without ever needing to
    touch or invalidate a notification that already referenced it.
    """

    class NotificationType(models.TextChoices):
        ADJUSTMENT_APPROVED = "ADJUSTMENT_APPROVED", "Adjustment Approved"
        ADJUSTMENT_REJECTED = "ADJUSTMENT_REJECTED", "Adjustment Rejected"
        ADJUSTMENT_SUBMITTED = "ADJUSTMENT_SUBMITTED", "Adjustment Submitted"

    # CASCADE (not PROTECT, unlike AuditLog.user) — notifications
    # are transient inbox items, not permanent historical records,
    # so it's correct for them to simply disappear if the owning
    # user account is ever deleted.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )

    notification_type = models.CharField(max_length=25, choices=NotificationType.choices)
    message = models.CharField(max_length=255)
    target_url = models.CharField(
        max_length=255,
        help_text="Where clicking this notification navigates to. Always generated server-side via reverse(), never user input.",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} — {self.message}"