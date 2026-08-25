"""
reports/views.py
────────────────────────────────────────────────────────────────
Manager-only analytical Reports page: 5 tabs (Activity, Products,
Categories, Locations, Adjustments) sharing one date-range selector.

Every report below queries warehouse.models directly, using
EXISTING data only — nothing here is invented statistics.
"""

from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.decorators import manager_required
from warehouse.models import AuditLog, Category, Inventory, Location, Product, StockAdjustmentRequest

VALID_TABS = {'activity', 'products', 'categories', 'locations', 'adjustments'}


def _resolve_date_range(request):
    """
    Turns the shared range control (?range=...&start=...&end=...)
    into a concrete (preset, start_date, end_date) tuple. Falls
    back to "Last 7 Days" for anything missing or invalid.
    """
    preset = request.GET.get('range', '7d')
    today = timezone.localdate()

    if preset == 'today':
        start, end = today, today
    elif preset == '30d':
        start, end = today - timedelta(days=29), today
    elif preset == 'this_month':
        start, end = today.replace(day=1), today
    elif preset == 'last_month':
        last_month_end = today.replace(day=1) - timedelta(days=1)
        start, end = last_month_end.replace(day=1), last_month_end
    elif preset == 'custom':
        start = parse_date(request.GET.get('start', '')) or today - timedelta(days=6)
        end = parse_date(request.GET.get('end', '')) or today
    else:
        preset = '7d'
        start, end = today - timedelta(days=6), today

    if start > end:
        start, end = end, start

    return preset, start, end


def _activity_report(start, end):
    """Units Received/Dispatched/Net, plus a daily trend line for the range."""
    logs = AuditLog.objects.filter(timestamp__date__gte=start, timestamp__date__lte=end)

    received = logs.filter(action_type=AuditLog.ActionType.INBOUND).aggregate(t=Sum('quantity_shift'))['t'] or 0
    dispatched = abs(logs.filter(action_type=AuditLog.ActionType.OUTBOUND).aggregate(t=Sum('quantity_shift'))['t'] or 0)

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    daily_rows = (
        logs.filter(action_type__in=[AuditLog.ActionType.INBOUND, AuditLog.ActionType.OUTBOUND])
        .annotate(day=TruncDate('timestamp'))
        .values('day', 'action_type')
        .annotate(total=Sum('quantity_shift'))
    )
    received_by_day = {d: 0 for d in days}
    dispatched_by_day = {d: 0 for d in days}
    for row in daily_rows:
        if row['day'] not in received_by_day:
            continue
        if row['action_type'] == AuditLog.ActionType.INBOUND:
            received_by_day[row['day']] = row['total']
        else:
            dispatched_by_day[row['day']] = abs(row['total'])

    return {
        'metrics': {'received': received, 'dispatched': dispatched, 'net': received - dispatched},
        'chart': {
            'labels': [d.strftime('%b %d') for d in days],
            'received': [received_by_day[d] for d in days],
            'dispatched': [dispatched_by_day[d] for d in days],
        },
    }


def _product_report(start, end):
    """
    Top 5 most received and most dispatched products, ranked by
    SKU (AuditLog's own text snapshot field). Axis labels stay as
    SKU (compact); a parallel "names" array is included so the
    frontend tooltip can show the full product name instead of
    repeating the SKU a second time.
    """
    logs = AuditLog.objects.filter(timestamp__date__gte=start, timestamp__date__lte=end)

    received_rows = (
        logs.filter(action_type=AuditLog.ActionType.INBOUND)
        .values('product_sku').annotate(total=Sum('quantity_shift')).order_by('-total')[:5]
    )
    dispatched_rows = (
        logs.filter(action_type=AuditLog.ActionType.OUTBOUND)
        .values('product_sku').annotate(total=Sum('quantity_shift')).order_by('total')[:5]
    )

    involved_skus = {r['product_sku'] for r in received_rows} | {r['product_sku'] for r in dispatched_rows}
    # Falls back to the SKU itself if the Product record no longer
    # matches (e.g. renamed/deleted since) — product_sku is a
    # deliberate text snapshot, not a live FK, so this lookup is
    # best-effort display convenience only.
    sku_to_name = dict(Product.objects.filter(sku__in=involved_skus).values_list('sku', 'name'))

    return {
        'metrics': {
            'products_received': logs.filter(action_type=AuditLog.ActionType.INBOUND).values('product_sku').distinct().count(),
            'products_dispatched': logs.filter(action_type=AuditLog.ActionType.OUTBOUND).values('product_sku').distinct().count(),
        },
        'most_received': {
            'labels': [r['product_sku'] for r in received_rows],
            'names': [sku_to_name.get(r['product_sku'], r['product_sku']) for r in received_rows],
            'values': [r['total'] for r in received_rows],
        },
        'most_dispatched': {
            'labels': [r['product_sku'] for r in dispatched_rows],
            'names': [sku_to_name.get(r['product_sku'], r['product_sku']) for r in dispatched_rows],
            'values': [abs(r['total']) for r in dispatched_rows],
        },
    }


def _category_report():
    """
    Product catalog composition by Category — % share of distinct
    SKUs per category (a Treemap), NOT physical stock units. This
    is deliberately a snapshot of current catalog structure, so it
    takes no date-range arguments at all: "how many product records
    exist in this category" has no historical dimension the way
    "units received" does. "Most Stocked Category" in the metric
    row above still uses physical units (unchanged) — the two
    numbers intentionally measure different things.
    """
    top_row = (
        Category.objects.annotate(total=Sum('products__inventory_records__quantity'))
        .values('name', 'total').order_by('-total').first()
    )
    top_category = top_row['name'] if top_row and top_row['total'] else '—'

    sku_counts = list(Category.objects.annotate(sku_count=Count('products')).values('name', 'sku_count'))
    total_skus = sum(row['sku_count'] for row in sku_counts) or 1

    return {
        'metrics': {
            'category_count': Category.objects.count(),
            'top_category': top_category,
        },
        'treemap_chart': {
            'labels': [row['name'] for row in sku_counts],
            'values': [row['sku_count'] for row in sku_counts],
            'percentages': [round(row['sku_count'] / total_skus * 100, 1) for row in sku_counts],
            'total_sku': total_skus,
        },
    }


def _location_report():
    """
    Top 10 locations by current units stored — a snapshot metric,
    not date-filtered. Also builds a per-location breakdown of
    exactly which products (and how many units of each) make up
    that total, so the chart's tooltip can show real composition
    instead of just one opaque number.
    """
    rows = (
        Location.objects.annotate(total=Sum('inventory_records__quantity'))
        .filter(total__gt=0).order_by('-total')[:10]
    )
    location_ids = [loc.pk for loc in rows]

    breakdown_qs = (
        Inventory.objects
        .filter(location_id__in=location_ids, quantity__gt=0)
        .select_related('product')
        .order_by('location_id', '-quantity')
    )
    breakdown_by_location = defaultdict(list)
    for inv in breakdown_qs:
        breakdown_by_location[inv.location_id].append({'name': inv.product.name, 'quantity': inv.quantity})

    return {
        'metrics': {
            'locations_used': Location.objects.filter(inventory_records__quantity__gt=0).distinct().count(),
            'total_locations': Location.objects.count(),
        },
        'chart': {
            'labels': [str(loc) for loc in rows],
            'values': [loc.total for loc in rows],
            'breakdown': [breakdown_by_location.get(loc.pk, []) for loc in rows],
        },
    }


def _adjustment_report(start, end):
    """Status breakdown, increase/decrease split, and a daily submission trend — all within the selected range."""
    qs = StockAdjustmentRequest.objects.filter(created_at__date__gte=start, created_at__date__lte=end)

    pending = qs.filter(status=StockAdjustmentRequest.Status.PENDING).count()
    approved = qs.filter(status=StockAdjustmentRequest.Status.APPROVED).count()
    rejected = qs.filter(status=StockAdjustmentRequest.Status.REJECTED).count()

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    daily_rows = qs.annotate(day=TruncDate('created_at')).values('day').annotate(total=Count('id'))
    counts_by_day = {d: 0 for d in days}
    for row in daily_rows:
        if row['day'] in counts_by_day:
            counts_by_day[row['day']] = row['total']

    return {
        'metrics': {
            'total': qs.count(),
            'pending': pending,
            'approved': approved,
            'rejected': rejected,
            'increases': qs.filter(quantity_change__gt=0).count(),
            'decreases': qs.filter(quantity_change__lt=0).count(),
        },
        'status_chart': {'labels': ['Pending', 'Approved', 'Rejected'], 'values': [pending, approved, rejected]},
        'trend_chart': {
            'labels': [d.strftime('%b %d') for d in days],
            'values': [counts_by_day[d] for d in days],
        },
    }


@login_required
@manager_required
def reports_home(request):
    """
    Manager-only analytical Reports page. Renders exactly one of
    the 5 report tabs per request, based on ?tab=.
    """
    tab = request.GET.get('tab', 'activity')
    if tab not in VALID_TABS:
        tab = 'activity'

    preset, start, end = _resolve_date_range(request)

    context = {
        'page_title': 'Reports',
        'tab': tab,
        'range_preset': preset,
        'range_start': start,
        'range_end': end,
    }

    if tab == 'activity':
        context['report'] = _activity_report(start, end)
    elif tab == 'products':
        context['report'] = _product_report(start, end)
    elif tab == 'categories':
        context['report'] = _category_report()
    elif tab == 'locations':
        context['report'] = _location_report()
    elif tab == 'adjustments':
        context['report'] = _adjustment_report(start, end)

    return render(request, 'reports/reports.html', context)