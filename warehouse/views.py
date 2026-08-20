"""
warehouse/views.py
────────────────────────────────────────────────────────────────
Thin views for warehouse workflows. Validation happens in
forms.py, business logic happens in services.py — these views only
coordinate the two and handle the HTTP request/response cycle.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import manager_required, staff_required

from . import services
from .forms import DispatchGoodsForm, ReceiveGoodsForm, StockAdjustmentRequestForm
from .models import StockAdjustmentRequest


@login_required
@staff_required
def receive_goods(request):
    """
    Staff-only page for recording inbound stock. On success, stays
    on this page with a fresh empty form so Staff can log several
    receipts in a row without extra navigation.
    """
    if request.method == 'POST':
        form = ReceiveGoodsForm(request.POST)
        if form.is_valid():
            try:
                services.receive_goods(
                    product=form.cleaned_data['product'],
                    location=form.cleaned_data['location'],
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                )
                messages.success(request, "Stock received successfully.")
                return redirect('warehouse:receive_goods')
            except ValidationError as e:
                messages.error(request, e.messages[0])
    else:
        form = ReceiveGoodsForm()

    return render(request, 'warehouse/receive_goods.html', {
        'form': form,
        'page_title': 'Receive Goods',
    })


@login_required
@staff_required
def dispatch_goods(request):
    """
    Staff-only page for recording outbound stock. Same pattern as
    receive_goods — success redirects back to a fresh form.
    """
    if request.method == 'POST':
        form = DispatchGoodsForm(request.POST)
        if form.is_valid():
            try:
                services.dispatch_goods(
                    product=form.cleaned_data['product'],
                    location=form.cleaned_data['location'],
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                )
                messages.success(request, "Stock dispatched successfully.")
                return redirect('warehouse:dispatch_goods')
            except ValidationError as e:
                messages.error(request, e.messages[0])
    else:
        form = DispatchGoodsForm()

    return render(request, 'warehouse/dispatch_goods.html', {
        'form': form,
        'page_title': 'Dispatch Goods',
        # Powers the Location dropdown's client-side chaining in
        # inventory_chain.js — see services.get_inventory_location_map().
        'inventory_map': services.get_inventory_location_map(),
    })


@login_required
@staff_required
def submit_adjustment_request(request):
    """
    Staff-only page for requesting a stock correction. Shows a
    submission form plus the Staff member's own 5 most recent
    requests with their current status.
    """
    if request.method == 'POST':
        form = StockAdjustmentRequestForm(request.POST)
        if form.is_valid():
            try:
                services.submit_adjustment_request(
                    product=form.cleaned_data['product'],
                    location=form.cleaned_data['location'],
                    staff_user=request.user,
                    quantity_change=form.cleaned_data['quantity_change'],
                    reason=form.cleaned_data['reason'],
                )
                messages.success(request, "Adjustment request submitted for review.")
                return redirect('warehouse:submit_adjustment_request')
            except ValidationError as e:
                messages.error(request, e.messages[0])
    else:
        form = StockAdjustmentRequestForm()

    recent_requests = (
        StockAdjustmentRequest.objects
        .filter(staff=request.user)
        .select_related('product', 'location')[:5]
    )

    return render(request, 'warehouse/adjustment_request.html', {
        'form': form,
        'page_title': 'Stock Adjustment Request',
        'recent_requests': recent_requests,
        'inventory_map': services.get_inventory_location_map(),
    })


@login_required
@manager_required
def adjustment_requests(request):
    """
    Manager-only review queue: every PENDING stock adjustment
    request, newest first.
    """
    pending_requests = (
        StockAdjustmentRequest.objects
        .filter(status=StockAdjustmentRequest.Status.PENDING)
        .select_related('product', 'location', 'staff')
    )

    return render(request, 'warehouse/adjustment_requests.html', {
        'page_title': 'Adjustment Requests',
        'pending_requests': pending_requests,
    })


@login_required
@manager_required
def approve_adjustment_request(request, pk):
    """
    Applies a PENDING request's quantity_change to Inventory via
    services.approve_adjustment, then returns to the review queue.
    """
    adjustment_request = get_object_or_404(StockAdjustmentRequest, pk=pk)
    if request.method == 'POST':
        try:
            services.approve_adjustment(adjustment_request, request.user)
            messages.success(request, f"Adjustment for {adjustment_request.product.sku} approved.")
        except ValidationError as e:
            messages.error(request, e.messages[0])
    return redirect('warehouse:adjustment_requests')


@login_required
@manager_required
def reject_adjustment_request(request, pk):
    """
    Marks a PENDING request REJECTED with no Inventory/AuditLog
    changes, per the confirmed workflow.
    """
    adjustment_request = get_object_or_404(StockAdjustmentRequest, pk=pk)
    if request.method == 'POST':
        try:
            services.reject_adjustment(adjustment_request, request.user)
            messages.success(request, f"Adjustment for {adjustment_request.product.sku} rejected.")
        except ValidationError as e:
            messages.error(request, e.messages[0])
    return redirect('warehouse:adjustment_requests')