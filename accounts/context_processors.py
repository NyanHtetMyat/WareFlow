"""
accounts/context_processors.py
────────────────────────────────────────────────────────────────
Injects the current user's recent notifications + unread count into
EVERY template's context, so the navbar's bell/popover renders
correctly on every authenticated page without each individual view
needing to fetch and pass this data itself.

This is the first context processor in the project — deliberately
deferred twice before (see the historical comments in
templates/components/sidebar.html and navbar.html) until a genuine
cross-cutting need existed. Notifications needing to appear
identically across ~25+ views is exactly that threshold; adding
'nav_unread_count': ... to every single view's context dict by hand
would have been real, spread-out duplication.
"""

from .models import Notification
from warehouse.models import StockAdjustmentRequest


def notifications(request):
    if not request.user.is_authenticated:
        return {}

    return {
        'nav_notifications': Notification.objects.filter(user=request.user).order_by('-created_at')[:15],
        'nav_unread_count': Notification.objects.filter(user=request.user, is_read=False).count(),
    }


def pending_adjustments_badge(request):
    """
    Makes the Manager sidebar's "Adjustment Requests" pending count
    available on every page, since the sidebar is shared app-wide —
    not just on the adjustment_requests view itself.

    Only queried for authenticated Managers. Staff/Admin never see
    this nav item, so there's no reason to run the query for them.
    """
    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'MANAGER':
        count = StockAdjustmentRequest.objects.filter(
            status=StockAdjustmentRequest.Status.PENDING
        ).count()
        return {'nav_pending_adjustments_count': count}
    return {'nav_pending_adjustments_count': 0}