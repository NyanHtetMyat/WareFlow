"""
warehouse/models.py
────────────────────────────────────────────────────────────────
Core domain models for WareFlow's warehouse app: Category,
Supplier, Location, Product, Inventory, StockAdjustmentRequest,
and AuditLog.

These implement the ER schema (WareFlow__ER.pdf / the DBML you
provided) as literally as possible. Every relationship's on_delete
behavior is a direct translation of the schema's `update`/`delete`
annotations — see the inline notes on any field where that required
interpretation rather than a 1:1 copy.
"""

from django.conf import settings
from django.db import models


class Category(models.Model):
    """
    A product category (e.g. "Electronics", "Stationery").

    Just a lookup table — no behavior beyond grouping Products.
    PROTECT: you cannot delete a Category while any Product still
    points at it (matches the ER schema's `delete: restrict` on
    the "classifies" relationship).
    """

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        # Shown in Django admin, shell, and anywhere a Category is
        # rendered as plain text — keeps debugging readable.
        return self.name


class Supplier(models.Model):
    """
    A goods supplier. Each Product points at exactly one Supplier.

    PROTECT: you cannot delete a Supplier while any Product still
    references it (matches `delete: restrict` on "supplies").
    """

    name = models.CharField(max_length=150, unique=True)
    contact_info = models.TextField(
        help_text="Free-text contact details (phone, email, address, etc.)."
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Location(models.Model):
    """
    A physical storage location, identified by zone/rack/bin
    (e.g. Zone A / Rack 14 / Bin 05).

    INHERITED DECISION: the (zone, rack, bin) combination is
    unique. This wasn't drawn explicitly in the ER diagram, but it
    was agreed in an earlier session and makes real-world sense —
    the same physical bin shouldn't be represented by two different
    rows. Flagging it here since it wasn't in the doc I re-read
    this session; remove the constraint below if you disagree.
    """

    zone = models.CharField(max_length=50, help_text="e.g. 'Zone A'")
    rack = models.CharField(max_length=50, help_text="e.g. 'Rack 14'")
    bin = models.CharField(max_length=50, help_text="e.g. 'Bin 05'")

    class Meta:
        ordering = ["zone", "rack", "bin"]
        constraints = [
            models.UniqueConstraint(
                fields=["zone", "rack", "bin"],
                name="unique_location_zone_rack_bin",
            )
        ]

    def __str__(self):
        # e.g. "Zone A / Rack 14 / Bin 05" — this exact format is
        # also what AuditLog.location_info snapshots later, so
        # keep this __str__ and that snapshot logic in sync when
        # you build the services layer.
        return f"{self.zone} / {self.rack} / {self.bin}"


class Product(models.Model):
    """
    A stockable item, identified by a unique SKU.

    low_stock_threshold is set per-product by a Manager when the
    product is created (confirmed decision — NOT a global setting),
    and can be edited later.
    """

    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)

    # PROTECT on both: a Category/Supplier still referenced by a
    # Product can't be deleted. Matches `delete: restrict` in the
    # ER schema for both "classifies" and "supplies".
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="products"
    )

    low_stock_threshold = models.PositiveIntegerField(
        default=0,
        help_text=(
            "Manager-defined threshold. When total quantity across all "
            "Locations falls at or below this number, the product should "
            "show up in low-stock reports/badges."
        ),
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.sku} — {self.name}"


class Inventory(models.Model):
    """
    The bridge/junction table resolving the Product <-> Location
    many-to-many relationship. Each row means "this many units of
    this Product currently sit at this Location."

    The (product, location) pair can only appear once — enforced
    below exactly as called for in the architecture doc, section 15.

    PROTECT on both FKs: you cannot delete a Product or a Location
    while an Inventory row still references it. This is what should
    power the "This location cannot be deleted because it currently
    contains inventory" message from the architecture doc's
    error-handling examples — Django raises ProtectedError here,
    which the service/view layer can catch and turn into that
    friendly message later.
    """

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="inventory_records"
    )
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="inventory_records"
    )
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["location", "product"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "location"],
                name="unique_inventory_per_product_location",
            )
        ]
        verbose_name_plural = "Inventory"

    def __str__(self):
        return f"{self.product.sku} @ {self.location} ({self.quantity})"


class StockAdjustmentRequest(models.Model):
    """
    A Staff-submitted request to correct a stock discrepancy at a
    specific Location. Sits at PENDING until a Manager approves or
    rejects it. Confirmed workflow: rejection does NOT require a
    reason on the manager's side.
    """

    class Status(models.TextChoices):
        # TextChoices (not a plain tuple) so we get
        # StockAdjustmentRequest.Status.PENDING instead of typing
        # the raw string "PENDING" everywhere — same pattern
        # accounts/models.py already uses for User.Role.
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="adjustment_requests"
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="adjustment_requests",
        help_text="Target bin where the discrepancy was found.",
    )

    # staff and manager both point at the same User model, so each
    # needs its own related_name — otherwise Django can't tell
    # "user.submitted_adjustments" apart from "user.reviewed_adjustments"
    # and throws a reverse-accessor clash at startup.
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_adjustments",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_adjustments",
        help_text="Populated once a Manager approves or rejects this request.",
    )

    quantity_change = models.IntegerField(
        help_text="Signed correction amount, e.g. -5 or +12. Can be negative."
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(
        null=True, blank=True, help_text="Set when a Manager approves/rejects."
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Adjustment #{self.pk} — {self.product.sku} ({self.status})"


class AuditLog(models.Model):
    """
    An immutable historical record of every inventory-affecting
    operation (receive, dispatch, adjustment approval).

    IMPORTANT DESIGN NOTE: product_sku and location_info are plain
    text SNAPSHOTS, not ForeignKeys — this is deliberate, straight
    from the ER schema. An audit record should keep showing exactly
    what the SKU / location string looked like at the moment the
    transaction happened, even if the real Product gets renamed or
    the Location gets restructured later. Don't "fix" these into
    ForeignKeys without discussing it first — that would quietly
    break the audit trail's whole purpose.

    FLAGGED CONFLICT — needs your confirmation before you migrate:
    The ER doc (WareFlow__ER.pdf / DBML) states `delete: restrict`
    for AuditLog.user_id, which is what's implemented below
    (PROTECT — a User can't be deleted while they have audit
    history). A note carried over from an earlier session claimed
    this should be SET NULL instead ("preserve history"), which
    contradicts the ER doc. I went with the ER doc's literal value
    since it's the authoritative schema document, but this is a
    one-line change if SET NULL is actually what you want — just
    confirm which is correct.
    """

    class ActionType(models.TextChoices):
        INBOUND = "INBOUND", "Inbound"
        OUTBOUND = "OUTBOUND", "Outbound"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    timestamp = models.DateTimeField(auto_now_add=True)

    # See "FLAGGED CONFLICT" note above before running migrations.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="audit_logs"
    )

    action_type = models.CharField(max_length=10, choices=ActionType.choices)
    product_sku = models.CharField(max_length=50)
    location_info = models.CharField(
        max_length=100, help_text="Snapshot string of Zone-Rack-Bin."
    )
    quantity_shift = models.IntegerField(
        help_text="Signed change, e.g. +42 for inbound, -18 for outbound."
    )
    resulting_quantity = models.PositiveIntegerField(
        help_text="Stock count in that bin immediately after this change."
    )

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action_type} — {self.product_sku} ({self.timestamp:%Y-%m-%d %H:%M})"