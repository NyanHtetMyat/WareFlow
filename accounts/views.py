"""
accounts/views.py
────────────────────────────────────────────────────────────────
Handles authentication: logging in, and sending users to the
correct starting page after login.
"""

from django.contrib.auth import login as auth_login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import WareFlowLoginForm, ProfileForm, ChangePasswordForm
from .models import Notification


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
    })