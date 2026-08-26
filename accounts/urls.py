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
    path('', views.dashboard_redirect, name='dashboard_redirect'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('notifications/<int:pk>/open/', views.notification_open, name='notification_open'),
]