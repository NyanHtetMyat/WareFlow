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
from django.shortcuts import redirect, render

from accounts.decorators import staff_required

from . import services
from .forms import DispatchGoodsForm, ReceiveGoodsForm


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
    })