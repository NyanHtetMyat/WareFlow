"""
reports/urls.py
────────────────────────────────────────────────────────────────
URL routes for the Manager Reports page.
"""

from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_home, name='reports_home'),
]