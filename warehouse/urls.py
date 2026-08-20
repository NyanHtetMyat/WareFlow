"""
warehouse/urls.py
────────────────────────────────────────────────────────────────
URL routes for warehouse workflows: receiving, dispatching,
inventory, products, suppliers, locations, and adjustments.

Only routes with a working view behind them are enabled below.
Remaining sidebar links stay as '#' placeholders (see sidebar.html's
inline TODO comments) until their views are built.
"""

from django.urls import path

from . import views

app_name = 'warehouse'

urlpatterns = [
    path('receive/', views.receive_goods, name='receive_goods'),
    path('dispatch/', views.dispatch_goods, name='dispatch_goods'),

    path('adjustments/submit/', views.submit_adjustment_request, name='submit_adjustment_request'),
    path('adjustments/', views.adjustment_requests, name='adjustment_requests'),
    path('adjustments/<int:pk>/approve/', views.approve_adjustment_request, name='approve_adjustment_request'),
    path('adjustments/<int:pk>/reject/', views.reject_adjustment_request, name='reject_adjustment_request'),
]