"""
accounts/services.py
────────────────────────────────────────────────────────────────
Notification creation logic. Lives here rather than in
warehouse/services.py since notifications are fundamentally about a
User's own inbox state, not warehouse domain data (see the design
note on Notification in models.py) — this file never imports
warehouse.models; callers there pass an already-loaded
StockAdjustmentRequest object and this file only reads plain
attributes off it (duck typing), keeping the dependency one-way.
"""

from django.urls import reverse

from .models import Notification, User


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