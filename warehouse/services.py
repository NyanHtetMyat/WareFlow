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
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AuditLog, Inventory, StockAdjustmentRequest


def _get_or_create_inventory(product, location):
    """
    Fetches the Inventory row for this product/location pair,
    creating one at quantity 0 if this is the first time stock has
    ever been recorded there.
    """
    inventory, _ = Inventory.objects.get_or_create(
        product=product, location=location
    )
    return inventory


def _create_audit_log(user, action_type, product, location, quantity_shift, resulting_quantity):
    """
    Shared helper so every stock-affecting operation snapshots the
    same fields the same way. product_sku/location_info are text
    snapshots (see the design note in models.py) rather than FKs,
    so this reads product.sku and str(location) at the moment of
    the transaction, not a live reference.
    """
    AuditLog.objects.create(
        user=user,
        action_type=action_type,
        product_sku=product.sku,
        location_info=str(location),
        quantity_shift=quantity_shift,
        resulting_quantity=resulting_quantity,
    )


@transaction.atomic
def receive_goods(product, location, quantity, user):
    """
    Records inbound stock. Increases the Inventory row for
    (product, location) by `quantity` and writes the matching
    AuditLog entry in the same transaction.
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
    negative — the view/form layer should catch ValidationError and
    surface it as "Insufficient stock."
    """
    if quantity <= 0:
        raise ValidationError("Quantity dispatched must be greater than zero.")

    try:
        inventory = Inventory.objects.get(product=product, location=location)
    except Inventory.DoesNotExist:
        raise ValidationError("No stock recorded for this product at this location.")

    if inventory.quantity < quantity:
        raise ValidationError("Insufficient stock at this location.")

    inventory.quantity -= quantity
    inventory.save()

    _create_audit_log(
        user=user,
        action_type=AuditLog.ActionType.OUTBOUND,
        product=product,
        location=location,
        quantity_shift=-quantity,
        resulting_quantity=inventory.quantity,
    )

    return inventory


def submit_adjustment_request(product, location, staff_user, quantity_change, reason):
    """
    Staff-initiated request to correct a stock discrepancy. Does
    NOT touch Inventory — only creates a PENDING record for a
    Manager to review later. Reason is required from Staff (checked
    here too, not just in the form, since services shouldn't assume
    every caller went through form validation).
    """
    if not reason or not reason.strip():
        raise ValidationError("A reason is required when submitting an adjustment request.")

    if quantity_change == 0:
        raise ValidationError("Quantity change cannot be zero.")

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
    Inventory, writes the audit trail, and marks the request
    APPROVED. Locks the Inventory row for the duration of the
    transaction so two near-simultaneous approvals touching the
    same product/location can't produce an inconsistent quantity.
    """
    if adjustment_request.status != StockAdjustmentRequest.Status.PENDING:
        raise ValidationError("Only pending adjustment requests can be approved.")

    inventory = _get_or_create_inventory(
        adjustment_request.product, adjustment_request.location
    )
    inventory = Inventory.objects.select_for_update().get(pk=inventory.pk)

    new_quantity = inventory.quantity + adjustment_request.quantity_change
    if new_quantity < 0:
        raise ValidationError("Approving this adjustment would result in negative stock.")

    inventory.quantity = new_quantity
    inventory.save()

    _create_audit_log(
        user=manager_user,
        action_type=AuditLog.ActionType.ADJUSTMENT,
        product=adjustment_request.product,
        location=adjustment_request.location,
        quantity_shift=adjustment_request.quantity_change,
        resulting_quantity=inventory.quantity,
    )

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