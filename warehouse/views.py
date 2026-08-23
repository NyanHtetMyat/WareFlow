"""
warehouse/views.py
────────────────────────────────────────────────────────────────
Thin views for warehouse workflows. Validation happens in
forms.py, business logic happens in services.py — these views only
coordinate the two and handle the HTTP request/response cycle.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import manager_required, role_required, staff_required
from accounts.models import User

from . import services
from .forms import (
    DispatchGoodsForm,
    ProductForm,
    ReceiveGoodsForm,
    StockAdjustmentRequestForm,
    SupplierForm,
)
from .models import Category, Inventory, Product, StockAdjustmentRequest, Supplier


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
    Inventory row. Read-only for both roles. Since Inventory rows
    are deleted at zero quantity (see services.py), every row shown
    here represents genuinely current stock.
    """
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    low_stock_only = request.GET.get('low_stock') == '1'
    sort = request.GET.get('sort', 'location')

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
        row.product_total = product_totals.get(row.product_id, 0)
        row.is_low_stock = row.product_id in low_stock_product_ids

    paginator = Paginator(inventory_rows, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

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


@login_required
@manager_required
def product_list(request):
    """
    Manager-only Product Management: view, search/filter, create,
    and edit Products. Stock status shown per product is DERIVED
    (never stored) from total Inventory quantity vs.
    low_stock_threshold, per the confirmed business rule:
        total >= threshold        -> OK
        0 < total < threshold     -> LOW STOCK
        total == 0 (or no rows)   -> OUT OF STOCK
    A Product with zero Inventory rows anywhere still appears here
    as Out of Stock — registering a Product doesn't require it to
    have ever been physically received.

    KPI stats (stocked/out-of-stock counts) are computed from ALL
    products regardless of the current search/filter, so they read
    as stable overview numbers rather than shifting with every
    search keystroke.
    """
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')

    all_totals = list(
        Product.objects.annotate(total_quantity=Sum('inventory_records__quantity')).values_list('total_quantity', flat=True)
    )
    stats = {
        'stocked_count': sum(1 for t in all_totals if t),
        'out_of_stock_count': sum(1 for t in all_totals if not t),
    }

    products_qs = (
        Product.objects
        .select_related('category', 'supplier')
        .annotate(total_quantity=Sum('inventory_records__quantity'))
    )

    if search_query:
        products_qs = products_qs.filter(Q(sku__icontains=search_query) | Q(name__icontains=search_query))

    if category_id:
        products_qs = products_qs.filter(category_id=category_id)

    products = list(products_qs.order_by('name'))

    for product in products:
        total = product.total_quantity or 0
        if total == 0:
            product.stock_status = 'out_of_stock'
        elif total < product.low_stock_threshold:
            product.stock_status = 'low_stock'
        else:
            product.stock_status = 'ok'

        # JSON blobs consumed by static/js/management_modals.js to
        # populate the Detail and Edit modals without a server
        # round-trip per row — the data's already on the page.
        product.detail_json = json.dumps({
            "SKU": product.sku,
            "Product Name": product.name,
            "Category": product.category.name,
            "Supplier": product.supplier.name,
            "Low-Stock Threshold": product.low_stock_threshold,
            "Total Stock": total,
            "Status": product.stock_status.replace('_', ' ').title(),
        })
        product.edit_json = json.dumps({
            "sku": product.sku,
            "name": product.name,
            "category": product.category_id,
            "supplier": product.supplier_id,
            "low_stock_threshold": product.low_stock_threshold,
        })

    if status_filter:
        products = [p for p in products if p.stock_status == status_filter]

    return render(request, 'warehouse/products.html', {
        'page_title': 'Products',
        'products': products,
        'categories': Category.objects.all(),
        'suppliers': Supplier.objects.all(),
        'search_query': search_query,
        'selected_category': category_id,
        'status_filter': status_filter,
        'stats': stats,
    })


@login_required
@manager_required
def product_create(request):
    """
    Handles the Add Product modal's POST. Always redirects back to
    the list — the modal doesn't stay open on failure (see the
    trade-off noted where this feature was introduced); a failed
    save surfaces its first error as a toast instead.
    """
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Product created successfully.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('warehouse:product_list')


@login_required
@manager_required
def product_edit(request, pk):
    """Handles the Edit Product modal's POST for an existing Product."""
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('warehouse:product_list')


@login_required
@manager_required
def supplier_list(request):
    """
    Manager-only Supplier Management: view, search, create, and
    edit Suppliers. Each row shows how many Products currently
    reference it — informational only, per the confirmed scope
    boundary keeping this page focused on Supplier data, not
    warehouse/inventory metrics.
    """
    search_query = request.GET.get('q', '').strip()

    suppliers_qs = Supplier.objects.annotate(product_count=Count('products')).prefetch_related('products')

    if search_query:
        suppliers_qs = suppliers_qs.filter(name__icontains=search_query)

    suppliers = list(suppliers_qs.order_by('name'))

    for supplier in suppliers:
        product_names = ", ".join(p.name for p in supplier.products.all()) or "—"
        supplier.detail_json = json.dumps({
            "Supplier Name": supplier.name,
            "Contact Info": supplier.contact_info,
            "Associated Products": product_names,
        })
        supplier.edit_json = json.dumps({
            "name": supplier.name,
            "contact_info": supplier.contact_info,
        })

    return render(request, 'warehouse/suppliers.html', {
        'page_title': 'Suppliers',
        'suppliers': suppliers,
        'search_query': search_query,
    })


@login_required
@manager_required
def supplier_create(request):
    """Handles the Add Supplier modal's POST."""
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Supplier created successfully.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('warehouse:supplier_list')


@login_required
@manager_required
def supplier_edit(request, pk):
    """Handles the Edit Supplier modal's POST for an existing Supplier."""
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, "Supplier updated successfully.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('warehouse:supplier_list')