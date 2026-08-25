"""
audit/views.py
────────────────────────────────────────────────────────────────
Read-only presentation of audit history. Per the architecture doc,
this app does not own or duplicate the AuditLog model — it queries
warehouse.models.AuditLog directly, the same way reports/ is meant
to query existing domain data rather than keeping its own copy.
"""

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from accounts.decorators import manager_required
from warehouse.models import AuditLog


@login_required
@manager_required
def audit_log_list(request):
    """
    Searchable, filterable, sortable, paginated view of every
    AuditLog entry — the permanent record of every inbound,
    outbound, and approved adjustment operation. Never editable
    from here; this page is read-only by design, matching the
    architecture doc's "audit records are historical, normal users
    cannot modify them" rule.
    """
    search_query = request.GET.get('q', '').strip()
    action_type = request.GET.get('action_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    sort_field = request.GET.get('sort', 'timestamp')
    sort_dir = request.GET.get('dir', 'desc')

    logs_qs = AuditLog.objects.select_related('user')

    if search_query:
        logs_qs = logs_qs.filter(
            Q(product_sku__icontains=search_query) | Q(location_info__icontains=search_query)
        )

    if action_type:
        logs_qs = logs_qs.filter(action_type=action_type)

    if date_from:
        logs_qs = logs_qs.filter(timestamp__date__gte=date_from)

    if date_to:
        logs_qs = logs_qs.filter(timestamp__date__lte=date_to)

    sort_map = {
        'timestamp': 'timestamp',
        'user': 'user__username',
        'action_type': 'action_type',
        'product_sku': 'product_sku',
        'quantity_shift': 'quantity_shift',
        'resulting_quantity': 'resulting_quantity',
    }
    order_field = sort_map.get(sort_field, 'timestamp')
    if sort_dir == 'desc':
        order_field = '-' + order_field
    logs_qs = logs_qs.order_by(order_field)

    paginator = Paginator(logs_qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    # product_sku is a deliberate text snapshot, not a live FK (see
    # the design note on AuditLog in models.py) — so the current
    # Product name is looked up separately, for display convenience
    # only, and only for the SKUs actually shown on this page. If a
    # SKU no longer matches any current Product, the name is simply
    # left blank rather than treated as an error — the audit record
    # itself remains complete and correct either way.
    from warehouse.models import Product
    sku_to_name = dict(
        Product.objects.filter(sku__in=[log.product_sku for log in page_obj.object_list])
        .values_list('sku', 'name')
    )
    for log in page_obj.object_list:
        log.product_name = sku_to_name.get(log.product_sku, '')
        log.original_quantity = log.resulting_quantity - log.quantity_shift

    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring = querystring.urlencode()

    return render(request, 'audit/audit_logs.html', {
        'page_title': 'Audit Logs',
        'page_obj': page_obj,
        'action_types': AuditLog.ActionType.choices,
        'search_query': search_query,
        'action_type': action_type,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort_field,
        'dir': sort_dir,
        'querystring': querystring,
    })