"""
warehouse/urls.py
────────────────────────────────────────────────────────────────
URL routes for warehouse workflows: receiving, dispatching,
inventory, products, suppliers, locations, and adjustments.
"""

from django.urls import path

from . import views

app_name = 'warehouse'

urlpatterns = [
    path('receive/', views.receive_goods, name='receive_goods'),
    path('dispatch/', views.dispatch_goods, name='dispatch_goods'),

    path('inventory/', views.inventory_list, name='inventory_list'),

    path('adjustments/submit/', views.submit_adjustment_request, name='submit_adjustment_request'),
    path('adjustments/', views.adjustment_requests, name='adjustment_requests'),
    path('adjustments/<int:pk>/approve/', views.approve_adjustment_request, name='approve_adjustment_request'),
    path('adjustments/<int:pk>/reject/', views.reject_adjustment_request, name='reject_adjustment_request'),

    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),

    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/create/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/edit/', views.supplier_edit, name='supplier_edit'),
]