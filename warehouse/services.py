"""
warehouse/services.py
────────────────────────────────────────────────────────────────
Business-logic layer for warehouse operations.

ZERO-QUANTITY RULE (applies throughout this file): an Inventory row
represents CURRENT physical stock. Whenever an operation below
brings a row's quantity down to exactly 0, that row is deleted —
the permanent record of it happening still lives in the AuditLog
entry created in the same transaction.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import AuditLog, Inventory, Location, Product, StockAdjustmentRequest


def _get_or_create_inventory(product, location):
    """
    Fetches the Inventory row for this product/location pair,
    creating one at quantity 0 if this is the first time stock has
    ever been recorded there. Only used by receive_goods().
    """
    inventory, _ = Inventory.objects.get_or_create(
        product=product, location=location
    )
    return inventory


def _create_audit_log(user, action_type, product, location, quantity_shift, resulting_quantity):
    """Shared helper so every stock-affecting operation snapshots the same fields the same way."""
    AuditLog.objects.create(
        user=user,
        action_type=action_type,
        product_sku=product.sku,
        location_info=str(location),
        quantity_shift=quantity_shift,
        resulting_quantity=resulting_quantity,
    )


def get_stocked_products():
    """
    Products that currently hold physical stock somewhere. Used
    for Dispatch/Decrease, which must target EXISTING stock — as
    opposed to Receive/Increase, which shows every product.
    """
    return (
        Product.objects
        .filter(inventory_records__quantity__gt=0)
        .distinct()
        .order_by('sku')
    )


def get_location_tree():
    """
    { zone: { rack: [{bin, id}, ...] } } for every REGISTERED
    Location, regardless of current stock. Powers the Zone->Rack->
    Bin cascade on Receive Goods and the Increase mode of Stock
    Adjustment Request, where any registered Location is a valid
    target per the confirmed business rules.
    """
    tree = {}
    for loc in Location.objects.all().order_by('zone', 'rack', 'bin'):
        zone_branch = tree.setdefault(loc.zone, {})
        rack_branch = zone_branch.setdefault(str(loc.rack), [])
        rack_branch.append({'bin': loc.bin, 'id': loc.pk})
    return tree


def get_inventory_location_tree():
    """
    { product_id: { zone: { rack: [{bin, id, quantity}, ...] } } }
    for every Product currently holding stock somewhere. Powers the
    Zone->Rack->Bin cascade on Dispatch and the Decrease mode of
    Stock Adjustment Request, where only Locations the selected
    Product currently occupies are valid targets.
    """
    tree = {}
    rows = (
        Inventory.objects
        .filter(quantity__gt=0)
        .select_related('location')
        .order_by('location__zone', 'location__rack', 'location__bin')
    )
    for row in rows:
        product_branch = tree.setdefault(str(row.product_id), {})
        zone_branch = product_branch.setdefault(row.location.zone, {})
        rack_branch = zone_branch.setdefault(str(row.location.rack), [])
        rack_branch.append({'bin': row.location.bin, 'id': row.location_id, 'quantity': row.quantity})
    return tree


def get_product_location_quantity_map():
    """
    Flat {"<product_id>:<location_id>": quantity} lookup built from
    every current Inventory row. Powers the "Current stock at this
    location" indicator on Receive Goods and the Increase mode of
    Stock Adjustment Request, where the selected pair may have NO
    existing Inventory row at all — a missing key simply means zero
    current stock, which the frontend reports as "No current stock
    at this location," per the confirmed indicator behavior.
    """
    return {
        f"{row['product_id']}:{row['location_id']}": row['quantity']
        for row in Inventory.objects.values('product_id', 'location_id', 'quantity')
    }


def compute_stock_status(total_quantity, threshold):
    """Shared OK / Low Stock / Out of Stock classification (Product Management + Manager Dashboard)."""
    total = total_quantity or 0
    if total == 0:
        return 'out_of_stock'
    if total < threshold:
        return 'low_stock'
    return 'ok'


def get_stock_status_counts():
    """Aggregate counts of Products in each derived stock-status bucket, for the Manager Dashboard."""
    counts = {'ok': 0, 'low_stock': 0, 'out_of_stock': 0}
    for total, threshold in Product.objects.annotate(
        total_quantity=Sum('inventory_records__quantity')
    ).values_list('total_quantity', 'low_stock_threshold'):
        counts[compute_stock_status(total, threshold)] += 1
    return counts


@transaction.atomic
def receive_goods(product, location, quantity, user):
    """Records inbound stock. The one operation allowed to create a brand-new Inventory row."""
    if quantity <= 0:
        raise ValidationError("Quantity received must be greater than zero.")

    inventory = _get_or_create_inventory(product, location)
    inventory.quantity += quantity
    inventory.save()

    _create_audit_log(
        user=user, action_type=AuditLog.ActionType.INBOUND,
        product=product, location=location,
        quantity_shift=quantity, resulting_quantity=inventory.quantity,
    )
    return inventory


@transaction.atomic
def dispatch_goods(product, location, quantity, user):
    """Records outbound stock. Deletes the Inventory row if it reaches exactly 0."""
    if quantity <= 0:
        raise ValidationError("Quantity dispatched must be greater than zero.")

    try:
        inventory = Inventory.objects.select_for_update().get(product=product, location=location)
    except Inventory.DoesNotExist:
        raise ValidationError("No stock recorded for this product at this location.")

    if inventory.quantity < quantity:
        raise ValidationError("Insufficient stock at this location.")

    new_quantity = inventory.quantity - quantity

    _create_audit_log(
        user=user, action_type=AuditLog.ActionType.OUTBOUND,
        product=product, location=location,
        quantity_shift=-quantity, resulting_quantity=new_quantity,
    )

    if new_quantity == 0:
        inventory.delete()
    else:
        inventory.quantity = new_quantity
        inventory.save()

    return new_quantity


def submit_adjustment_request(product, location, staff_user, quantity_change, reason):
    """
    Staff-initiated request to correct a stock discrepancy.

    INCREASE requests (quantity_change > 0) do NOT require an
    existing Inventory row. A Product can have real physical stock
    at a Location even when its Inventory row was previously
    deleted by the zero-quantity rule after an earlier dispatch —
    an Increase adjustment is precisely the mechanism for
    correcting that: it's treated as 0 current stock at submission
    time, and approve_adjustment() will create the row if it still
    doesn't exist by the time it's approved. This is deliberately
    kept as a SEPARATE operation from receive_goods() — Inbound
    represents newly received goods, Increase represents correcting
    a discrepancy in existing (or previously-existing) stock.

    DECREASE requests (quantity_change < 0) still require an
    EXISTING Inventory row — you cannot decrease stock that isn't
    currently recorded anywhere.
    """
    if not reason or not reason.strip():
        raise ValidationError("A reason is required when submitting an adjustment request.")

    if quantity_change == 0:
        raise ValidationError("Quantity change cannot be zero.")

    inventory = Inventory.objects.filter(product=product, location=location).first()

    if quantity_change < 0:
        if inventory is None:
            raise ValidationError(
                "No existing inventory found for this product at this location. "
                "Decrease adjustments require existing stock to correct."
            )
        if inventory.quantity + quantity_change < 0:
            raise ValidationError(
                f"This decrease would exceed the available stock "
                f"({inventory.quantity} units currently at this location)."
            )

    return StockAdjustmentRequest.objects.create(
        product=product, location=location, staff=staff_user,
        quantity_change=quantity_change, reason=reason,
        status=StockAdjustmentRequest.Status.PENDING,
    )


@transaction.atomic
def approve_adjustment(adjustment_request, manager_user):
    """
    Applies an approved request's quantity_change to Inventory.

    INCREASE requests may CREATE the Inventory row if it doesn't
    already exist by approval time — this is what makes Increase
    able to correct a Product-Location combination whose row was
    previously deleted by the zero-quantity rule. DECREASE requests
    continue to require an EXISTING row; approval is refused if the
    row is missing (e.g. fully dispatched and deleted sometime
    between submission and review).
    """
    if adjustment_request.status != StockAdjustmentRequest.Status.PENDING:
        raise ValidationError("Only pending adjustment requests can be approved.")

    is_increase = adjustment_request.quantity_change > 0

    if is_increase:
        inventory, _ = Inventory.objects.get_or_create(
            product=adjustment_request.product, location=adjustment_request.location,
        )
        inventory = Inventory.objects.select_for_update().get(pk=inventory.pk)
    else:
        try:
            inventory = Inventory.objects.select_for_update().get(
                product=adjustment_request.product, location=adjustment_request.location,
            )
        except Inventory.DoesNotExist:
            raise ValidationError(
                "No existing inventory found for this product at this location. "
                "It may have been fully dispatched since this request was submitted."
            )

    new_quantity = inventory.quantity + adjustment_request.quantity_change
    if new_quantity < 0:
        raise ValidationError("Approving this adjustment would result in negative stock.")

    _create_audit_log(
        user=manager_user, action_type=AuditLog.ActionType.ADJUSTMENT,
        product=adjustment_request.product, location=adjustment_request.location,
        quantity_shift=adjustment_request.quantity_change, resulting_quantity=new_quantity,
    )

    if new_quantity == 0:
        inventory.delete()
    else:
        inventory.quantity = new_quantity
        inventory.save()

    adjustment_request.status = StockAdjustmentRequest.Status.APPROVED
    adjustment_request.manager = manager_user
    adjustment_request.reviewed_at = timezone.now()
    adjustment_request.save()
    return adjustment_request


def reject_adjustment(adjustment_request, manager_user):
    """Marks a PENDING request REJECTED. No Inventory/AuditLog changes. No reason required from the Manager."""
    if adjustment_request.status != StockAdjustmentRequest.Status.PENDING:
        raise ValidationError("Only pending adjustment requests can be rejected.")

    adjustment_request.status = StockAdjustmentRequest.Status.REJECTED
    adjustment_request.manager = manager_user
    adjustment_request.reviewed_at = timezone.now()
    adjustment_request.save()
    return adjustment_request