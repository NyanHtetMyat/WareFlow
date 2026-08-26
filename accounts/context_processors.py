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


def notifications(request):
    if not request.user.is_authenticated:
        return {}

    return {
        'nav_notifications': Notification.objects.filter(user=request.user).order_by('-created_at')[:15],
        'nav_unread_count': Notification.objects.filter(user=request.user, is_read=False).count(),
    }