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
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import manager_required, role_required, staff_required
from accounts.models import User

from . import services
from .forms import DispatchGoodsForm, ReceiveGoodsForm, StockAdjustmentRequestForm
from .models import Category, Inventory, Product, StockAdjustmentRequest


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


@login_required
@role_required(User.Role.STAFF, User.Role.MANAGER)
def inventory_list(request):
    """
    Searchable, filterable, paginated view of every current
    Inventory row. Read-only for both roles — Staff's confirmed
    workflows imply they need to see current stock, and Manager's
    confirmed permission explicitly includes "view entire inventory
    in detail." Stock itself only ever changes via Receive/Dispatch/
    Adjustment, never from this page.

    Since Inventory rows are deleted at zero quantity (see the
    zero-quantity rule in services.py), every row shown here
    represents genuinely current stock — there's no need to filter
    out dead/zeroed positions separately.
    """
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    low_stock_only = request.GET.get('low_stock') == '1'
    sort = request.GET.get('sort', 'location')

    # Per-product totals + which products are low-stock, computed
    # once via a single annotated query rather than one query per
    # row further down. "Low stock" is checked against the TOTAL
    # across all locations, per Product.low_stock_threshold's own
    # help_text in models.py — not any single location's quantity.
    products_with_totals = Product.objects.annotate(total_quantity=Sum('inventory_records__quantity'))
    product_totals = dict(products_with_totals.values_list('id', 'total_quantity'))
    low_stock_product_ids = set(
        products_with_totals
        .filter(total_quantity__isnull=False, total_quantity__lte=F('low_stock_threshold'))
        .values_list('id', flat=True)
    )

    inventory_qs = Inventory.objects.select_related('product', 'product__category', 'location')

    if search_query:
        inventory_qs = inventory_qs.filter(
            Q(product__sku__icontains=search_query) | Q(product__name__icontains=search_query)
        )

    if category_id:
        inventory_qs = inventory_qs.filter(product__category_id=category_id)

    if low_stock_only:
        inventory_qs = inventory_qs.filter(product_id__in=low_stock_product_ids)

    sort_map = {
        'location': ('location__zone', 'location__rack', 'location__bin'),
        'product': ('product__name',),
        'quantity_asc': ('quantity',),
        'quantity_desc': ('-quantity',),
    }
    inventory_qs = inventory_qs.order_by(*sort_map.get(sort, sort_map['location']))

    inventory_rows = list(inventory_qs)
    for row in inventory_rows:
        # Attached in Python rather than annotated in SQL — simpler
        # to read here since product_totals/low_stock_product_ids
        # were already computed above for the KPI cards anyway.
        row.product_total = product_totals.get(row.product_id, 0)
        row.is_low_stock = row.product_id in low_stock_product_ids

    paginator = Paginator(inventory_rows, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Preserves search/filter/sort when clicking a pagination link —
    # without this, page 2 would silently drop whatever was typed
    # into the search box on page 1.
    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring = querystring.urlencode()

    return render(request, 'warehouse/inventory_list.html', {
        'page_title': 'Inventory',
        'page_obj': page_obj,
        'categories': Category.objects.all(),
        'search_query': search_query,
        'selected_category': category_id,
        'low_stock_only': low_stock_only,
        'sort': sort,
        'querystring': querystring,
        'stats': {
            'stocked_products': sum(1 for total in product_totals.values() if total),
            'total_units': Inventory.objects.aggregate(total=Sum('quantity'))['total'] or 0,
            'low_stock_count': len(low_stock_product_ids),
            'locations_used': Inventory.objects.values('location_id').distinct().count(),
        },
    })