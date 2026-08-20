"""
warehouse/services.py
────────────────────────────────────────────────────────────────
Business-logic layer for warehouse operations.

Views should call these functions rather than manipulating
Inventory or AuditLog rows directly. Keeping the logic here means
every inbound/outbound/adjustment operation gets the same
transactional guarantee (inventory change + audit log entry
succeed or fail together) without duplicating that guarantee in
every view that happens to touch stock.

ZERO-QUANTITY RULE (applies throughout this file): an Inventory row
represents CURRENT physical stock. Whenever an operation below
brings a row's quantity down to exactly 0, that row is deleted —
the permanent record of it happening still lives in the AuditLog
entry created in the same transaction, so no history is lost.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AuditLog, Inventory, Product, StockAdjustmentRequest


def _get_or_create_inventory(product, location):
    """
    Fetches the Inventory row for this product/location pair,
    creating one at quantity 0 if this is the first time stock has
    ever been recorded there. Only used by receive_goods() — every
    other stock-changing operation below must target an EXISTING
    row and should never silently create one (see
    submit_adjustment_request() and approve_adjustment()).
    """
    inventory, _ = Inventory.objects.get_or_create(
        product=product, location=location
    )
    return inventory


def _create_audit_log(user, action_type, product, location, quantity_shift, resulting_quantity):
    """
    Shared helper so every stock-affecting operation snapshots the
    same fields the same way. product_sku/location_info are text
    snapshots (see the design note in models.py) rather than FKs.
    """
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
    Products that currently hold physical stock somewhere (at least
    one Inventory row with quantity > 0).

    Used to populate the Product dropdown for operations that must
    target EXISTING stock — Dispatch and Stock Adjustment Request —
    as opposed to Receive/Inbound, which intentionally shows every
    product in the catalog since receiving is what creates a
    product's very first Inventory row.
    """
    return (
        Product.objects
        .filter(inventory_records__quantity__gt=0)
        .distinct()
        .order_by('sku')
    )


def get_inventory_location_map():
    """
    Builds { "<product_id>": [{"id", "label", "quantity"}, ...] }
    for every product currently holding stock somewhere.

    Embedded as JSON into the Dispatch and Stock Adjustment Request
    pages so their Location dropdown can be populated instantly,
    client-side, once a Product is chosen — no extra server
    round-trip needed. This is a UX convenience only: it does not
    replace the authoritative Product+Location pair check that
    dispatch_goods() / submit_adjustment_request() /
    approve_adjustment() still perform below regardless of what the
    UI happened to offer.
    """
    inventory_map = {}
    rows = (
        Inventory.objects
        .filter(quantity__gt=0)
        .select_related('location')
        .order_by('location__zone', 'location__rack', 'location__bin')
    )
    for row in rows:
        inventory_map.setdefault(str(row.product_id), []).append({
            'id': row.location_id,
            'label': str(row.location),
            'quantity': row.quantity,
        })
    return inventory_map


@transaction.atomic
def receive_goods(product, location, quantity, user):
    """
    Records inbound stock. This is the ONE operation allowed to
    create a brand-new Inventory row from nothing — a Product can
    legitimately exist in the catalog with zero physical stock until
    its first delivery arrives, and this is that moment.
    """
    if quantity <= 0:
        raise ValidationError("Quantity received must be greater than zero.")

    inventory = _get_or_create_inventory(product, location)
    inventory.quantity += quantity
    inventory.save()

    _create_audit_log(
        user=user,
        action_type=AuditLog.ActionType.INBOUND,
        product=product,
        location=location,
        quantity_shift=quantity,
        resulting_quantity=inventory.quantity,
    )

    return inventory


@transaction.atomic
def dispatch_goods(product, location, quantity, user):
    """
    Records outbound stock. Decreases the Inventory row for
    (product, location) by `quantity`. Refuses to let stock go
    negative. If this dispatch brings quantity down to exactly 0,
    the Inventory row is deleted per the zero-quantity rule — the
    row represents CURRENT stock, and there's no current stock left
    to represent once it hits zero. select_for_update() locks the
    row for the transaction so two near-simultaneous dispatches
    against the same row can't both succeed and push it negative.
    """
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
        user=user,
        action_type=AuditLog.ActionType.OUTBOUND,
        product=product,
        location=location,
        quantity_shift=-quantity,
        resulting_quantity=new_quantity,
    )

    if new_quantity == 0:
        inventory.delete()
    else:
        inventory.quantity = new_quantity
        inventory.save()

    return new_quantity


def submit_adjustment_request(product, location, staff_user, quantity_change, reason):
    """
    Staff-initiated request to correct a stock discrepancy. Does
    NOT touch Inventory — only creates a PENDING record for a
    Manager to review later.

    Per the confirmed business rule, adjustments correct EXISTING
    physical stock positions only — they are not a hidden
    replacement for Receive/Inbound. The Product dropdown on the
    form is already filtered to only offer currently-stocked
    products (see forms.py), but that's a UI convenience only — this
    check here is the actual backend enforcement of the same rule,
    independent of whatever the form happened to show.
    """
    if not reason or not reason.strip():
        raise ValidationError("A reason is required when submitting an adjustment request.")

    if quantity_change == 0:
        raise ValidationError("Quantity change cannot be zero.")

    if not Inventory.objects.filter(product=product, location=location).exists():
        raise ValidationError(
            "No existing inventory found for this product at this location. "
            "Use Receive Goods if this product has just arrived."
        )

    return StockAdjustmentRequest.objects.create(
        product=product,
        location=location,
        staff=staff_user,
        quantity_change=quantity_change,
        reason=reason,
        status=StockAdjustmentRequest.Status.PENDING,
    )


@transaction.atomic
def approve_adjustment(adjustment_request, manager_user):
    """
    Manager approves a PENDING request: applies quantity_change to
    the EXISTING Inventory row for (product, location), writes the
    audit trail, and marks the request APPROVED.

    Per the confirmed business rule, adjustments must NOT invent a
    new Inventory row the way receive_goods() does — if no row
    exists by approval time (e.g. the location was fully dispatched
    and its row deleted sometime between submission and review),
    approval is refused rather than silently recreating it. If the
    approved change brings quantity down to exactly 0, the row is
    deleted per the zero-quantity rule, same as dispatch_goods().
    """
    if adjustment_request.status != StockAdjustmentRequest.Status.PENDING:
        raise ValidationError("Only pending adjustment requests can be approved.")

    try:
        inventory = Inventory.objects.select_for_update().get(
            product=adjustment_request.product,
            location=adjustment_request.location,
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
        user=manager_user,
        action_type=AuditLog.ActionType.ADJUSTMENT,
        product=adjustment_request.product,
        location=adjustment_request.location,
        quantity_shift=adjustment_request.quantity_change,
        resulting_quantity=new_quantity,
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
    """
    Manager rejects a PENDING request. No Inventory or AuditLog
    changes happen on rejection — just records who reviewed it and
    when. No reason required from the Manager (confirmed workflow).
    """
    if adjustment_request.status != StockAdjustmentRequest.Status.PENDING:
        raise ValidationError("Only pending adjustment requests can be rejected.")

    adjustment_request.status = StockAdjustmentRequest.Status.REJECTED
    adjustment_request.manager = manager_user
    adjustment_request.reviewed_at = timezone.now()
    adjustment_request.save()

    return adjustment_request