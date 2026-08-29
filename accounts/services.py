"""
accounts/services.py
────────────────────────────────────────────────────────────────
Two related groups of logic:
  1. Notification creation — lives here rather than in
     warehouse/services.py since notifications are fundamentally
     about a User's own inbox state, not warehouse domain data (see
     the design note on Notification in models.py). This file never
     imports warehouse.models; callers there pass an already-loaded
     StockAdjustmentRequest object and this file only reads plain
     attributes off it (duck typing), keeping the dependency
     one-way.
  2. Password Reset Request workflow — submit / complete / reject,
     the accounts-app equivalent of warehouse.services' Stock
     Adjustment Request approve/reject functions.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import Notification, PasswordResetRequest, User


def _format_quantity(quantity_change):
    return f"{'+' if quantity_change > 0 else ''}{quantity_change}"


def notify_staff_adjustment_reviewed(adjustment_request, approved):
    """
    Notifies the Staff member who submitted a request once a
    Manager approves or rejects it. Links back to the Staff
    member's own Stock Adjustment Request page, where their recent
    requests list already shows the resulting status.
    """
    verb = "approved" if approved else "rejected"
    Notification.objects.create(
        user=adjustment_request.staff,
        notification_type=(
            Notification.NotificationType.ADJUSTMENT_APPROVED if approved
            else Notification.NotificationType.ADJUSTMENT_REJECTED
        ),
        message=(
            f"Stock adjustment {verb} — {adjustment_request.product.name} "
            f"{_format_quantity(adjustment_request.quantity_change)}"
        ),
        target_url=reverse('warehouse:submit_adjustment_request'),
    )


def notify_managers_new_adjustment_request(adjustment_request):
    """
    Notifies every active Manager that a new request needs review.
    Creates ONE Notification row PER Manager (not one shared row),
    so each Manager's read/unread state is independent — one
    Manager opening it must never mark it read for any other.
    """
    message = (
        f"New stock adjustment request — {adjustment_request.product.name} "
        f"{_format_quantity(adjustment_request.quantity_change)}"
    )
    target_url = reverse('warehouse:adjustment_requests')

    managers = User.objects.filter(role=User.Role.MANAGER, is_active=True)
    Notification.objects.bulk_create([
        Notification(
            user=manager,
            notification_type=Notification.NotificationType.ADJUSTMENT_SUBMITTED,
            message=message,
            target_url=target_url,
        )
        for manager in managers
    ])


def notify_admins_new_password_reset_request(reset_request):
    """
    Notifies every active Admin that a new password reset request
    needs review. Same one-row-per-recipient pattern as
    notify_managers_new_adjustment_request above.
    """
    message = f"Password reset requested — {reset_request.user.username}"
    target_url = reverse('accounts:password_reset_requests')

    admins = User.objects.filter(role=User.Role.ADMIN, is_active=True)
    Notification.objects.bulk_create([
        Notification(
            user=admin,
            notification_type=Notification.NotificationType.PASSWORD_RESET_REQUESTED,
            message=message,
            target_url=target_url,
        )
        for admin in admins
    ])


def submit_password_reset_request(identifier):
    """
    Looks up a user by username OR email (case-insensitive) and
    files a PENDING PasswordResetRequest for them, unless one is
    already pending.

    Deliberately returns normally — never raises, never signals
    success/failure back to the caller — for BOTH "no matching
    account" and "already has one pending" outcomes. The public
    Forgot Password page must never reveal whether a given
    username/email exists in the system (account enumeration), so
    the view always shows the same generic confirmation regardless
    of what happened here.
    """
    user = User.objects.filter(
        Q(username__iexact=identifier) | Q(email__iexact=identifier)
    ).first()

    if user is None:
        return

    already_pending = PasswordResetRequest.objects.filter(
        user=user, status=PasswordResetRequest.Status.PENDING
    ).exists()
    if already_pending:
        return

    reset_request = PasswordResetRequest.objects.create(user=user)
    notify_admins_new_password_reset_request(reset_request)


def complete_password_reset_request(reset_request, admin_user):
    """
    Resets the requesting user's password to the fixed system
    default (settings.DEFAULT_RESET_PASSWORD — identical mechanism
    to accounts.views.user_reset_password) and marks this specific
    request COMPLETED. Combined into one operation since a request
    without an eventual password reset serves no purpose.
    """
    if reset_request.status != PasswordResetRequest.Status.PENDING:
        raise ValidationError("Only pending password reset requests can be completed.")

    reset_request.user.set_password(settings.DEFAULT_RESET_PASSWORD)
    reset_request.user.save(update_fields=['password'])

    reset_request.status = PasswordResetRequest.Status.COMPLETED
    reset_request.resolved_by = admin_user
    reset_request.resolved_at = timezone.now()
    reset_request.save()
    return reset_request


def reject_password_reset_request(reset_request, admin_user, rejection_reason=""):
    """Marks a PENDING request REJECTED, with no password change."""
    if reset_request.status != PasswordResetRequest.Status.PENDING:
        raise ValidationError("Only pending password reset requests can be rejected.")

    reset_request.status = PasswordResetRequest.Status.REJECTED
    reset_request.resolved_by = admin_user
    reset_request.resolved_at = timezone.now()
    reset_request.rejection_reason = rejection_reason
    reset_request.save()
    return reset_request