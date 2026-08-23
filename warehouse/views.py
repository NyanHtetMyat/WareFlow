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

# Shared across Inventory and Product sorting — Status isn't a real
# database column on either page (it's derived from quantity vs.
# threshold), so "sort by Status" is resolved to this numeric rank
# in Python rather than in SQL. Ascending therefore reads
# OK -> Low Stock -> Out of Stock, matching the confirmed spec.
STOCK_STATUS_RANK = {'ok': 0, 'low_stock': 1, 'out_of_stock': 2}

STOCK_STATUS_BADGE = {
    'ok': {'cls': 'status-badge--approved', 'icon': 'bi-check-circle', 'text': 'OK'},
    'low_stock': {'cls': 'status-badge--warning', 'icon': 'bi-exclamation-triangle', 'text': 'Low Stock'},
    'out_of_stock': {'cls': 'status-badge--rejected', 'icon': 'bi-x-octagon', 'text': 'Out of Stock'},
}


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
    Searchable, filterable, sortable, paginated view of every
    current Inventory row. Sorting happens in Python on the fully
    materialized row list (not via queryset.order_by()) so that
    "Status" — a derived value, not a real column — can be sorted
    with exactly the same code path as every other column, rather
    than needing special-case handling.
    """
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    low_stock_only = request.GET.get('low_stock') == '1'
    sort_field = request.GET.get('sort', 'location')
    sort_dir = request.GET.get('dir', 'asc')

    products_with_totals = Product.objects.annotate(total_quantity=Sum('inventory_records__quantity'))
    product_totals = dict(products_with_totals.values_list('id', 'total_quantity'))
    low_stock_product_ids = set(
        products_with_totals
        .filter(total_quantity__isnull=False, total_quantity__lte=F('low_stock_threshold'))
        .values_list('id', flat=True)
    )

    inventory_qs = (
        Inventory.objects
        .select_related('product', 'product__category', 'location')
        .order_by('pk')  # stable base order so Python sort below has deterministic tie-breaking
    )

    if search_query:
        inventory_qs = inventory_qs.filter(
            Q(product__sku__icontains=search_query) | Q(product__name__icontains=search_query)
        )

    if category_id:
        inventory_qs = inventory_qs.filter(product__category_id=category_id)

    if low_stock_only:
        inventory_qs = inventory_qs.filter(product_id__in=low_stock_product_ids)

    inventory_rows = list(inventory_qs)
    for row in inventory_rows:
        row.product_total = product_totals.get(row.product_id, 0)
        row.is_low_stock = row.product_id in low_stock_product_ids
        row.status_rank = STOCK_STATUS_RANK['low_stock' if row.is_low_stock else 'ok']

    def sort_key(row):
        return {
            'product': row.product.name.lower(),
            'category': row.product.category.name.lower(),
            'location': str(row.location),
            'quantity_here': row.quantity,
            'total_stock': row.product_total,
            'status': row.status_rank,
        }.get(sort_field, str(row.location))

    inventory_rows.sort(key=sort_key, reverse=(sort_dir == 'desc'))

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
        'sort': sort_field,
        'dir': sort_dir,
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
    Manager-only Product Management: view, search/filter/sort,
    create, and edit Products. Stock status is DERIVED, never
    stored, computed fresh from total Inventory quantity vs.
    low_stock_threshold on every request.
    """
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    sort_field = request.GET.get('sort', 'name')
    sort_dir = request.GET.get('dir', 'asc')

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
        .order_by('pk')
    )

    if search_query:
        products_qs = products_qs.filter(Q(sku__icontains=search_query) | Q(name__icontains=search_query))

    if category_id:
        products_qs = products_qs.filter(category_id=category_id)

    products = list(products_qs)

    for product in products:
        total = product.total_quantity or 0
        if total == 0:
            product.stock_status = 'out_of_stock'
        elif total < product.low_stock_threshold:
            product.stock_status = 'low_stock'
        else:
            product.stock_status = 'ok'

        product.detail_json = json.dumps({
            "SKU": product.sku,
            "Product Name": product.name,
            "Category": product.category.name,
            "Supplier": product.supplier.name,
            "Low-Stock Threshold": product.low_stock_threshold,
            "Total Stock": total,
            # A dict (not a plain string) here is a signal to
            # management_modals.js to render this as a colored
            # status badge instead of plain text — see STOCK_STATUS_BADGE.
            "Status": {"__type": "badge", **STOCK_STATUS_BADGE[product.stock_status]},
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

    def sort_key(p):
        return {
            'sku': p.sku.lower(),
            'name': p.name.lower(),
            'category': p.category.name.lower(),
            'supplier': p.supplier.name.lower(),
            'threshold': p.low_stock_threshold,
            'status': STOCK_STATUS_RANK[p.stock_status],
        }.get(sort_field, p.name.lower())

    products.sort(key=sort_key, reverse=(sort_dir == 'desc'))

    return render(request, 'warehouse/products.html', {
        'page_title': 'Products',
        'products': products,
        'categories': Category.objects.all(),
        'suppliers': Supplier.objects.all(),
        'search_query': search_query,
        'selected_category': category_id,
        'status_filter': status_filter,
        'sort': sort_field,
        'dir': sort_dir,
        'stats': stats,
    })


@login_required
@manager_required
def product_create(request):
    """
    Handles the Add Product modal's POST. Always redirects back to
    the list; a failed save surfaces its first error as a toast.
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
    Manager-only Supplier Management: view, search/sort, create,
    and edit Suppliers. Each row shows how many Products currently
    reference it.
    """
    search_query = request.GET.get('q', '').strip()
    sort_field = request.GET.get('sort', 'name')
    sort_dir = request.GET.get('dir', 'asc')

    suppliers_qs = (
        Supplier.objects
        .annotate(product_count=Count('products'))
        .prefetch_related('products')
        .order_by('pk')
    )

    if search_query:
        suppliers_qs = suppliers_qs.filter(name__icontains=search_query)

    suppliers = list(suppliers_qs)

    for supplier in suppliers:
        # A plain list (not a joined string) — management_modals.js
        # renders this as a bulleted list in the detail modal rather
        # than one long comma-separated line.
        product_names = list(supplier.products.values_list('name', flat=True))
        supplier.detail_json = json.dumps({
            "Supplier Name": supplier.name,
            "Contact Info": supplier.contact_info,
            "Associated Products": product_names,
        })
        supplier.edit_json = json.dumps({
            "name": supplier.name,
            "contact_info": supplier.contact_info,
        })

    def sort_key(s):
        return {
            'name': s.name.lower(),
            'contact_info': s.contact_info.lower(),
            'product_count': s.product_count,
        }.get(sort_field, s.name.lower())

    suppliers.sort(key=sort_key, reverse=(sort_dir == 'desc'))

    return render(request, 'warehouse/suppliers.html', {
        'page_title': 'Suppliers',
        'suppliers': suppliers,
        'search_query': search_query,
        'sort': sort_field,
        'dir': sort_dir,
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