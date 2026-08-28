"""
accounts/urls.py
────────────────────────────────────────────────────────────────
URL routes for authentication and account-related pages.
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.dashboard_redirect, name='dashboard_redirect'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('notifications/<int:pk>/open/', views.notification_open, name='notification_open'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
]