"""
audit/urls.py
────────────────────────────────────────────────────────────────
URL routes for the audit history view.
"""

from django.urls import path

from . import views

app_name = 'audit'

urlpatterns = [
    path('', views.audit_log_list, name='audit_logs'),
]