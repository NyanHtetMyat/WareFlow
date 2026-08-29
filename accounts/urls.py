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
    path('users/', views.user_management, name='user_management'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/<int:pk>/reset-password/', views.user_reset_password, name='user_reset_password'),
]