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
from django.utils import timezone

from accounts.decorators import manager_required, role_required, staff_required
from accounts.models import User

from . import services
from .forms import (
    CategoryForm,
    DispatchGoodsForm,
    LocationForm,
    ProductForm,
    ReceiveGoodsForm,
    StockAdjustmentRequestForm,
    SupplierForm,
)
from .models import AuditLog, Category, Inventory, Location, Product, StockAdjustmentRequest, Supplier

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
    Staff-only page for recording inbound stock. Product uses a
    searchable combobox; Location uses a Zone->Rack->Bin cascade
    restricted only to REGISTERED locations (unrestricted by
    Product) — see static/js/location_cascade.js.
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

    product_options = [
        {'id': p.id, 'sku': p.sku, 'name': p.name, 'supplier_name': p.supplier.name}
        for p in Product.objects.select_related('supplier').order_by('sku')
    ]

    return render(request, 'warehouse/receive_goods.html', {
        'form': form,
        'page_title': 'Receive Goods',
        'product_options': product_options,
        'location_tree': services.get_location_tree(),
        'stock_lookup': services.get_product_location_quantity_map(),
    })


@login_required
@staff_required
def dispatch_goods(request):
    """
    Staff-only page for recording outbound stock. Product-first
    cascade: Zone/Rack/Bin stay locked until a Product is chosen,
    then restricted to only that Product's current stock locations.
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

    product_options = [
        {'id': p.id, 'sku': p.sku, 'name': p.name}
        for p in services.get_stocked_products()
    ]

    return render(request, 'warehouse/dispatch_goods.html', {
        'form': form,
        'page_title': 'Dispatch Goods',
        'product_options': product_options,
        'inventory_tree': services.get_inventory_location_tree(),
    })


@login_required
@staff_required
def submit_adjustment_request(request):
    """
    Staff-only page for requesting a stock correction. Increase
    mode behaves like Receive Goods (any Product, any registered
    Location); Decrease mode behaves like Dispatch (Product-first,
    restricted to that Product's current stock locations).

    "Your Recent Requests" below the form has two tabs — Pending
    and History (approved/rejected) — each independently paginated
    at 10 rows, matching every other table in the project.
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

    history_tab = request.GET.get('tab', 'pending')
    if history_tab not in ('pending', 'history'):
        history_tab = 'pending'

    requests_qs = StockAdjustmentRequest.objects.filter(staff=request.user).select_related('product', 'location')
    if history_tab == 'pending':
        requests_qs = requests_qs.filter(status=StockAdjustmentRequest.Status.PENDING)
    else:
        requests_qs = requests_qs.exclude(status=StockAdjustmentRequest.Status.PENDING)

    paginator = Paginator(requests_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring = querystring.urlencode()

    all_products = [{'id': p.id, 'sku': p.sku, 'name': p.name} for p in Product.objects.order_by('sku')]
    stocked_products = [{'id': p.id, 'sku': p.sku, 'name': p.name} for p in services.get_stocked_products()]

    return render(request, 'warehouse/adjustment_request.html', {
        'form': form,
        'page_title': 'Stock Adjustment Request',
        'history_tab': history_tab,
        'page_obj': page_obj,
        'querystring': querystring,
        'increase_product_options': all_products,
        'decrease_product_options': stocked_products,
        'increase_location_tree': services.get_location_tree(),
        'decrease_location_tree': services.get_inventory_location_tree(),
        'stock_lookup': services.get_product_location_quantity_map(),
    })


@login_required
@manager_required
def adjustment_requests(request):
    """Manager-only review queue: every PENDING request, newest first, paginated at 10."""
    pending_requests = (
        StockAdjustmentRequest.objects
        .filter(status=StockAdjustmentRequest.Status.PENDING)
        .select_related('product', 'location', 'staff')
    )

    paginator = Paginator(pending_requests, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring = querystring.urlencode()

    return render(request, 'warehouse/adjustment_requests.html', {
        'page_title': 'Adjustment Requests',
        'page_obj': page_obj,
        'querystring': querystring,
        'pending_count': pending_requests.count(),
    })


@login_required
@manager_required
def approve_adjustment_request(request, pk):
    """Applies a PENDING request's quantity_change to Inventory."""
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
    """Marks a PENDING request REJECTED with no Inventory changes."""
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
    """Searchable, filterable, sortable, paginated Inventory view."""
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
        .order_by('pk')
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
def master_data(request):
    """
    Manager-only navigation hub linking to the four master-data
    management pages. Consolidating Products/Suppliers/Categories/
    Locations behind one sidebar entry (instead of four separate
    top-level items) is what keeps the Manager sidebar short enough
    that Logout never gets pushed below the visible viewport.
    """
    return render(request, 'warehouse/master_data.html', {
        'page_title': 'Master Data',
    })


@login_required
@manager_required
def product_list(request):
    """Manager-only Product Management: search/filter/sort, create, edit."""
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
        product.stock_status = services.compute_stock_status(total, product.low_stock_threshold)

        product.detail_json = json.dumps({
            "SKU": product.sku,
            "Product Name": product.name,
            "Category": product.category.name,
            "Supplier": product.supplier.name,
            "Low-Stock Threshold": product.low_stock_threshold,
            "Total Stock": total,
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

    paginator = Paginator(products, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring = querystring.urlencode()

    return render(request, 'warehouse/products.html', {
        'page_title': 'Products',
        'breadcrumb_parent_label': 'Master Data',
        'breadcrumb_parent_url_name': 'warehouse:master_data',
        'page_obj': page_obj,
        'querystring': querystring,
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
    """Handles the Add Product modal's POST."""
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
    """Handles the Edit Product modal's POST."""
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
    """Manager-only Supplier Management: search/sort, create, edit."""
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

    paginator = Paginator(suppliers, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring = querystring.urlencode()

    return render(request, 'warehouse/suppliers.html', {
        'page_title': 'Suppliers',
        'breadcrumb_parent_label': 'Master Data',
        'breadcrumb_parent_url_name': 'warehouse:master_data',
        'page_obj': page_obj,
        'querystring': querystring,
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
    """Handles the Edit Supplier modal's POST."""
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, "Supplier updated successfully.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('warehouse:supplier_list')


@login_required
@manager_required
def category_list(request):
    """
    Manager-only Category Management: search/sort, create, edit.
    Architecture note: Category management was originally slated as
    an Admin-only page, but this was deliberately changed to a
    Manager permission per project decision.
    """
    search_query = request.GET.get('q', '').strip()
    sort_field = request.GET.get('sort', 'name')
    sort_dir = request.GET.get('dir', 'asc')

    categories_qs = Category.objects.annotate(product_count=Count('products')).order_by('pk')

    if search_query:
        categories_qs = categories_qs.filter(name__icontains=search_query)

    categories = list(categories_qs)

    for category in categories:
        product_names = list(category.products.values_list('name', flat=True))
        category.detail_json = json.dumps({
            "Category Name": category.name,
            "Products in this Category": product_names,
        })
        category.edit_json = json.dumps({
            "name": category.name,
        })

    def sort_key(c):
        return {
            'name': c.name.lower(),
            'product_count': c.product_count,
        }.get(sort_field, c.name.lower())
    
    categories.sort(key=sort_key, reverse=(sort_dir == 'desc'))

    paginator = Paginator(categories, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring = querystring.urlencode()

    return render(request, 'warehouse/categories.html', {
        'page_title': 'Categories',
        'breadcrumb_parent_label': 'Master Data',
        'breadcrumb_parent_url_name': 'warehouse:master_data',        
        'page_obj': page_obj,
        'querystring': querystring,
        'search_query': search_query,
        'sort': sort_field,
        'dir': sort_dir,
    })


@login_required
@manager_required
def category_create(request):
    """Handles the Add Category modal's POST."""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created successfully.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('warehouse:category_list')


@login_required
@manager_required
def category_edit(request, pk):
    """Handles the Edit Category modal's POST."""
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated successfully.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('warehouse:category_list')


@login_required
@manager_required
def location_list(request):
    """
    Manager-only Location Management: search/sort, create, edit.
    Architecture note: same deliberate change as Category above —
    originally Admin-only per the architecture doc, moved to
    Manager per project decision.
    """
    search_query = request.GET.get('q', '').strip()
    sort_field = request.GET.get('sort', 'location')
    sort_dir = request.GET.get('dir', 'asc')

    locations_qs = (
        Location.objects
        .annotate(stocked_count=Count('inventory_records', filter=Q(inventory_records__quantity__gt=0)))
        .prefetch_related('inventory_records__product')
        .order_by('pk')
    )

    locations = list(locations_qs)

    if search_query:
        # Matched against the canonical "A-R01-B01" string, not the
        # raw zone/rack/bin fields separately — a search for the
        # full code (or any substring of it, e.g. "R01" or just "A")
        # wouldn't match anything meaningful against the split
        # fields, since rack/bin are stored as plain integers, not
        # the zero-padded display strings. Filtered in Python since
        # Location count is small (same reasoning as the sort logic
        # below, which already materializes this list).
        normalized_query = search_query.strip().upper()
        locations = [loc for loc in locations if normalized_query in str(loc)]

    for location in locations:
        product_names = [inv.product.name for inv in location.inventory_records.all() if inv.quantity > 0]
        location.detail_json = json.dumps({
            "Location Code": str(location),
            "Zone": location.zone,
            "Rack": location.rack,
            "Bin": location.bin,
            "Products Stocked Here": product_names,
        })
        location.edit_json = json.dumps({
            "zone": location.zone,
            "rack": location.rack,
            "bin": location.bin,
        })

    def sort_key(loc):
        return {
            'location': (loc.zone, loc.rack, loc.bin),
            'zone': loc.zone,
            'rack': loc.rack,
            'bin': loc.bin,
            'stocked_count': loc.stocked_count,
        }.get(sort_field, (loc.zone, loc.rack, loc.bin))
    
    locations.sort(key=sort_key, reverse=(sort_dir == 'desc'))

    paginator = Paginator(locations, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring = querystring.urlencode()

    return render(request, 'warehouse/locations.html', {
        'page_title': 'Locations',
        'breadcrumb_parent_label': 'Master Data',
        'breadcrumb_parent_url_name': 'warehouse:master_data',        
        'page_obj': page_obj,
        'querystring': querystring,
        'search_query': search_query,
        'sort': sort_field,
        'dir': sort_dir,
    })


@login_required
@manager_required
def location_create(request):
    """Handles the Add Location modal's POST."""
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Location created successfully.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('warehouse:location_list')


@login_required
@manager_required
def location_edit(request, pk):
    """Handles the Edit Location modal's POST."""
    location = get_object_or_404(Location, pk=pk)
    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            messages.success(request, "Location updated successfully.")
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    return redirect('warehouse:location_list')


@login_required
@staff_required
def staff_dashboard(request):
    """
    Staff's own daily activity overview. Deliberately lightweight
    per the confirmed scope: no charts, no quick-action buttons —
    the sidebar already covers navigation to Receive/Dispatch/
    Adjustments directly. Just today's numbers and today's own
    transaction history.
    """
    today = timezone.localdate()
    today_logs_qs = (
        AuditLog.objects
        .filter(user=request.user, timestamp__date=today)
        .order_by('-timestamp')
    )

    received_today = today_logs_qs.filter(
        action_type=AuditLog.ActionType.INBOUND
    ).aggregate(total=Sum('quantity_shift'))['total'] or 0

    dispatched_today = abs(
        today_logs_qs.filter(action_type=AuditLog.ActionType.OUTBOUND)
        .aggregate(total=Sum('quantity_shift'))['total'] or 0
    )

    pending_count = StockAdjustmentRequest.objects.filter(
        staff=request.user, status=StockAdjustmentRequest.Status.PENDING
    ).count()

    today_logs = list(today_logs_qs)

    # product_sku is a text snapshot, not a live FK (see the design
    # note on AuditLog in models.py) — Product names are looked up
    # separately, for display only, same pattern as audit/views.py.
    sku_to_name = dict(
        Product.objects.filter(sku__in=[log.product_sku for log in today_logs]).values_list('sku', 'name')
    )
    for log in today_logs:
        log.product_name = sku_to_name.get(log.product_sku, '')

    return render(request, 'warehouse/staff_dashboard.html', {
        'page_title': 'Dashboard',
        'stats': {
            'received_today': received_today,
            'dispatched_today': dispatched_today,
            'pending_count': pending_count,
            'transaction_count': len(today_logs),
        },
        'today_logs': today_logs,
    })


@login_required
@manager_required
def manager_dashboard(request):
    """
    Manager's operational overview. Deliberately concise per the
    confirmed scope: KPI cards plus ONE simple 7-day Received vs
    Dispatched trend chart. Deeper analytics/comparisons are
    reserved for the future Reports page, not duplicated here.
    """
    today = timezone.localdate()

    stock_counts = services.get_stock_status_counts()

    today_logs = AuditLog.objects.filter(timestamp__date=today)
    received_today = today_logs.filter(
        action_type=AuditLog.ActionType.INBOUND
    ).aggregate(total=Sum('quantity_shift'))['total'] or 0
    dispatched_today = abs(
        today_logs.filter(action_type=AuditLog.ActionType.OUTBOUND)
        .aggregate(total=Sum('quantity_shift'))['total'] or 0
    )
    pending_count = StockAdjustmentRequest.objects.filter(
        status=StockAdjustmentRequest.Status.PENDING
    ).count()
    total_products = Product.objects.count()

    return render(request, 'warehouse/manager_dashboard.html', {
        'page_title': 'Dashboard',
        'stock_counts': stock_counts,
        'stats': {
            'total_products': total_products,
            'received_today': received_today,
            'dispatched_today': dispatched_today,
            'pending_count': pending_count,
        },
    })