"""
accounts/views.py
────────────────────────────────────────────────────────────────
Handles authentication: logging in, and sending users to the
correct starting page after login.
"""

from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import WareFlowLoginForm


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
    messages.info(request, "You are Logged out")
    
    # 3. Redirect to your login page (or home page)
    return redirect('accounts:login')


@login_required
def dashboard_redirect(request):
    """
    Sends a logged-in user to their correct starting page based on role.

    Currently renders a temporary placeholder page, since the warehouse
    and reports apps (and their dashboard views) haven't been built yet.
    Once those exist, this will redirect instead of rendering a page:
        STAFF   -> reports:staff_dashboard
        MANAGER -> reports:manager_dashboard
        ADMIN   -> accounts:user_management
    """
    return render(request, 'accounts/placeholder_dashboard.html', {
        'role': request.user.get_role_display(),
    })