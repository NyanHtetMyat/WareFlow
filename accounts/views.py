"""
accounts/views.py
────────────────────────────────────────────────────────────────
Handles authentication: logging in, and sending users to the
correct starting page after login.
"""

import json

from django.conf import settings
from django.contrib.auth import login as auth_login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .decorators import admin_required
from .forms import WareFlowLoginForm, ProfileForm, ChangePasswordForm, AdminUserEditForm, AdminUserCreateForm
from .models import Notification, User

# Role badge styling + sort rank, shared by the table and the
# detail overlay below — one place to update if a role's color
# ever changes.
ROLE_BADGE = {
    User.Role.STAFF: {'cls': 'status-badge--role-staff', 'icon': 'bi-person-badge'},
    User.Role.MANAGER: {'cls': 'status-badge--role-manager', 'icon': 'bi-person-badge'},
    User.Role.ADMIN: {'cls': 'status-badge--role-admin', 'icon': 'bi-shield-lock'},
}
ROLE_RANK = {User.Role.STAFF: 0, User.Role.MANAGER: 1, User.Role.ADMIN: 2}


def login_view(request):
    """
    Displays and processes the login form.

    GET  -> shows an empty login form.
    POST -> validates credentials and logs the user in.
    """
    if request.user.is_authenticated:
        # Already logged in, no reason to show the login page again.
        return redirect('accounts:dashboard_redirect')

    if request.method == 'POST':
        form = WareFlowLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, "Logged In Successfully")
            return redirect('accounts:dashboard_redirect')
    else:
        form = WareFlowLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    # 1. Clear the session / log the user out
    logout(request)

    # 2. Show Alert to user
    messages.info(request, "You have Logged out")
    
    # 3. Redirect to your login page (or home page)
    return redirect('accounts:login')


@login_required
def dashboard_redirect(request):
    """
    Sends a logged-in user to their correct starting page based on
    role. STAFF and MANAGER now have real dashboards — they live in
    the warehouse app (not reports/), a deliberate architecture
    decision: these are quick operational overviews, not deep
    analytics, so they sit alongside the operations they summarize.
    Deeper analysis is reserved for the future Reports page instead.

    ADMIN still renders the placeholder — Admin functionality
    remains explicitly out of scope for now.
    """
    if request.user.is_staff_role:
        return redirect('warehouse:staff_dashboard')

    if request.user.is_manager:
        return redirect('warehouse:manager_dashboard')

    return render(request, 'accounts/placeholder_dashboard.html', {
        'role': request.user.get_role_display(),
    })


@login_required
def notification_open(request, pk):
    """
    Marks a notification as read and redirects to its target page.
    Ownership-checked via user=request.user in the lookup — a user
    can never mark or view another user's notification by guessing
    a pk. Plain GET is intentional: opening a notification IS the
    read action from the user's perspective (like opening an
    email), not a destructive operation needing POST protection.
    """
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return redirect(notification.target_url)


@login_required
def profile_view(request):
    """
    Own-profile view/edit page. Only first_name, last_name, and
    image are ever editable here — see ProfileForm in forms.py for
    why that's enforced structurally, not just visually.
    """
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)

    return render(request, 'accounts/profile.html', {
        'page_title': 'My Profile',
        'profile_user': request.user,
        'form': form,
    })


@login_required
def change_password_view(request):
    """
    Lets any authenticated user (any role) change their own
    password. update_session_auth_hash keeps them logged in
    afterward — Django invalidates the session on password change
    by default, which would otherwise log the user out mid-flow.
    """
    if request.method == 'POST':
        form = ChangePasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully.")
            return redirect('accounts:profile')
    else:
        form = ChangePasswordForm(user=request.user)

    return render(request, 'accounts/change_password.html', {
        'page_title': 'Change Password',
        'form': form,
        'breadcrumb_parent_label': 'My Profile',
        'breadcrumb_parent_url_name': 'accounts:profile',
    })


@login_required
@admin_required
def user_management(request):
    """
    Admin-only user directory: search, filter, sort, paginate every
    WareFlow account. Read-only listing — editing, deactivation,
    and password resets are each a SEPARATE action below, not
    combined into one giant form.
    """
    search_query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    sort_field = request.GET.get('sort', 'username')
    sort_dir = request.GET.get('dir', 'asc')

    users_qs = User.objects.all().order_by('pk')

    if search_query:
        users_qs = users_qs.filter(Q(username__icontains=search_query) | Q(email__icontains=search_query))

    if role_filter:
        users_qs = users_qs.filter(role=role_filter)

    if status_filter == 'enabled':
        users_qs = users_qs.filter(is_active=True)
    elif status_filter == 'disabled':
        users_qs = users_qs.filter(is_active=False)

    users = list(users_qs)

    for u in users:
        # Table's "Full Name" column follows the confirmed rule
        # exactly, including "-" for neither name set — deliberately
        # NOT reusing display_name here, since that property falls
        # back to username for this exact case, which the table
        # explicitly should not do.
        if u.first_name and u.last_name:
            u.full_name_display = f"{u.first_name} {u.last_name}"
        elif u.first_name:
            u.full_name_display = u.first_name
        elif u.last_name:
            u.full_name_display = u.last_name
        else:
            u.full_name_display = "-"

        u.is_self = (u.pk == request.user.pk)

        # Split into two blobs: header_json feeds a compact custom
        # avatar+name+role header (populated by a small page-local
        # script — see user_management.html), while detail_json
        # keeps only the fields still shown as generic rows via
        # management_modals.js's shared renderer. Avoiding repeating
        # Full Name/Role/Photo in BOTH places is what actually fixes
        # the overlay's excessive height.
        u.header_json = json.dumps({
            "image_url": u.image.url if u.image else "",
            "avatar_initial": u.avatar_initial,
            "role": u.role.lower(),
            "full_name": u.display_name,
            "role_badge": {"cls": ROLE_BADGE[u.role]['cls'], "icon": ROLE_BADGE[u.role]['icon'], "text": u.get_role_display()},
        })
        u.detail_json = json.dumps({
            "First Name": u.first_name or "-",
            "Last Name": u.last_name or "-",
            "Username": u.username,
            "Email": u.email,
            "Account Status": (
                {"__type": "badge", "cls": "status-badge--approved", "icon": "bi-check-circle", "text": "Enabled"}
                if u.is_active else
                {"__type": "badge", "cls": "status-badge--rejected", "icon": "bi-x-circle", "text": "Disabled"}
            ),
            "Date Joined": u.date_joined.strftime("%b %d, %Y"),
        })
        u.edit_json = json.dumps({
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "role": u.role,
        })

    def sort_key(u):
        return {
            'username': u.username.lower(),
            'email': u.email.lower(),
            'full_name': u.full_name_display.lower(),
            'role': ROLE_RANK[u.role],
            'status': 0 if u.is_active else 1,
        }.get(sort_field, u.username.lower())

    users.sort(key=sort_key, reverse=(sort_dir == 'desc'))

    paginator = Paginator(users, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring = querystring.urlencode()

    return render(request, 'accounts/user_management.html', {
        'page_title': 'User Management',
        'page_obj': page_obj,
        'querystring': querystring,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'sort': sort_field,
        'dir': sort_dir,
        'role_choices': User.Role.choices,
    })


@login_required
@admin_required
def user_edit(request, pk):
    """
    Admin edits another user's Email/First Name/Last Name/Role.
    Username is never touched here. Blocked against the Admin's own
    account — self-editing role/email through this bulk action path
    is disallowed the same way self-deactivation already is in
    user_toggle_active below; use My Profile for editing your own
    details instead.
    """
    target_user = get_object_or_404(User, pk=pk)

    if target_user.pk == request.user.pk:
        messages.error(request, "You can't edit your own account here. Use My Profile instead.")
        return redirect('accounts:user_management')

    if target_user.role == User.Role.ADMIN:
        # Editing is fully unavailable for OTHER Admin accounts too,
        # not just self — Reset Password remains the only permitted
        # action against another Admin (see user_reset_password,
        # unchanged). Checked before the POST branch so a request
        # crafted directly against this URL is blocked the same way.
        messages.error(request, "Admin accounts cannot be edited. Only a password reset is available.")
        return redirect('accounts:user_management')

    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, instance=target_user)
        if form.is_valid():
            form.save()
            messages.success(request, f"{target_user.username}'s account was updated.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('accounts:user_management')


@login_required
@admin_required
def user_create(request):
    """
    Admin creates a brand new Staff or Manager account (role choices
    are narrowed to those two inside AdminUserCreateForm — see
    forms.py). No password is collected from the Admin: every new
    account is created with the fixed system default password
    (settings.DEFAULT_RESET_PASSWORD), the same mechanism the
    existing "Reset Password" action already uses. The new user is
    expected to change it via My Profile > Change Password after
    their first login.
    """
    if request.method == 'POST':
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save(commit=False)
            new_user.set_password(settings.DEFAULT_RESET_PASSWORD)
            new_user.save()
            messages.success(request, f"{new_user.username}'s account was created with the default password.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('accounts:user_management')


@login_required
@admin_required
def user_toggle_active(request, pk):
    """
    Deactivates or reactivates a user account. A dedicated POST-only
    action confirmed via a modal on the frontend — deliberately NOT
    a field inside the ordinary Edit form, per the confirmed
    requirement that activation state is an explicit account
    action. Never permitted against the Admin's own account, to
    prevent accidental self-lockout.
    """
    target_user = get_object_or_404(User, pk=pk)

    if target_user.pk == request.user.pk:
        messages.error(request, "You can't deactivate your own account.")
        return redirect('accounts:user_management')

    if target_user.role == User.Role.ADMIN:
        # Admin accounts are protected from deactivation/reactivation
        # entirely — not just self-protection. This is checked before
        # the POST branch below so it also blocks the action even if
        # a request is crafted directly against this URL.
        messages.error(request, "Admin accounts cannot be deactivated or reactivated.")
        return redirect('accounts:user_management')

    if request.method == 'POST':
        target_user.is_active = not target_user.is_active
        target_user.save(update_fields=['is_active'])
        verb = "reactivated" if target_user.is_active else "deactivated"
        messages.success(request, f"{target_user.username}'s account was {verb}.")

    return redirect('accounts:user_management')


@login_required
@admin_required
def user_reset_password(request, pk):
    """
    Resets a user's password to the fixed system default
    (settings.DEFAULT_RESET_PASSWORD). Deliberately separate from
    both ordinary profile editing AND the user's own Change
    Password flow (which requires their CURRENT password — this
    doesn't, since it's an administrative override).
    """
    target_user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        target_user.set_password(settings.DEFAULT_RESET_PASSWORD)
        target_user.save(update_fields=['password'])
        messages.success(request, f"{target_user.username}'s password was reset to the system default.")
    return redirect('accounts:user_management')