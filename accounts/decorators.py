"""
accounts/decorators.py
────────────────────────────────────────────────────────────────
Server-side role-enforcement decorators.

Per the architecture doc (Section 12): hiding a nav item from a
role is a UI convenience only, never the actual security boundary.
Every view whose functionality is role-restricted must also check
that role here, independent of whatever the sidebar shows.
"""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import User


def role_required(*allowed_roles):
    """
    Restricts a view to users whose `role` is one of `allowed_roles`.

    Usage: @role_required(User.Role.STAFF, User.Role.MANAGER)

    Always pair this with @login_required, applied ABOVE it, e.g.:
        @login_required
        @role_required(User.Role.STAFF)
        def some_view(request): ...
    login_required must run first — an anonymous user has no
    `.role` attribute, so this decorator assumes it's only ever
    reached by an authenticated user.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                messages.error(request, "You do not have permission to access that page.")
                return redirect('accounts:dashboard_redirect')
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def staff_required(view_func):
    """Shortcut for the common case of a Staff-only view."""
    return role_required(User.Role.STAFF)(view_func)


def manager_required(view_func):
    """Shortcut for the common case of a Manager-only view."""
    return role_required(User.Role.MANAGER)(view_func)


def admin_required(view_func):
    """Shortcut for the common case of an Admin-only view."""
    return role_required(User.Role.ADMIN)(view_func)