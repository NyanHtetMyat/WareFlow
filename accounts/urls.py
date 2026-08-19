"""
accounts/urls.py
────────────────────────────────────────────────────────────────
URL routes for authentication and account-related pages.
"""

from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'accounts'

urlpatterns = [
    # Root landing page — sends logged-in users to the right starting point
    path('', views.dashboard_redirect, name='dashboard_redirect'),

    # Login page
    path('login/', views.login_view, name='login'),

    # Logout — Django's built-in view handles session cleanup.
    # Redirect target comes from LOGOUT_REDIRECT_URL in settings.py.
    # path('logout/', LogoutView.as_view(), name='logout'),
    path('logout/', views.logout_view, name='logout'),
]