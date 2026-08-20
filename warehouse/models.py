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
from django.core.validators import MinValueValidator, RegexValidator
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
    A physical storage location, identified by zone/rack/bin.

    Rack and bin are stored as plain integers, never as formatted
    text — "01" is a DISPLAY concern only, handled entirely in
    __str__() below. Storing "Rack 01" or "B01" directly in these
    fields is exactly what this design avoids: it was the source of
    inconsistent, hard-to-read records before this change (a Staff
    member could previously type "Rack 01" in one row and "01" in
    another for the same physical shelf).

    Canonical display format: {ZONE}-R{RACK:02d}-B{BIN:02d}
        zone="A", rack=1, bin=1   -> "A-R01-B01"
        zone="B", rack=12, bin=4  -> "B-R12-B04"

    The (zone, rack, bin) combination is unique — the same physical
    bin should never be represented by two different rows.
    """

    zone = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                r'^[A-Za-z]+$',
                "Zone must contain letters only, e.g. 'A' or 'B' — no numbers or spaces.",
            )
        ],
        help_text="Short alphabetic zone code, e.g. 'A'. Stored uppercase automatically.",
    )
    rack = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Rack number, 1 or greater. Stored as a plain number, not 'R01'.",
    )
    bin = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Bin number, 1 or greater. Stored as a plain number, not 'B01'.",
    )

    class Meta:
        ordering = ["zone", "rack", "bin"]
        constraints = [
            models.UniqueConstraint(
                fields=["zone", "rack", "bin"],
                name="unique_location_zone_rack_bin",
            )
        ]

    def save(self, *args, **kwargs):
        # Normalizes casing at the database level so "a" and "A" can
        # never accidentally become two different zones — enforced
        # here rather than only in a form, so this holds true even
        # for rows created via the Django admin or the shell.
        self.zone = self.zone.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        # This exact format is what every dropdown, audit log
        # snapshot, and review card displays across the whole app —
        # changing this one line changes the format everywhere.
        return f"{self.zone}-R{self.rack:02d}-B{self.bin:02d}"


class Product(models.Model):
    """
    A stockable item, identified by a unique SKU.

    low_stock_threshold is set per-product by a Manager when the
    product is created, and can be edited later.
    """

    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)

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

    IMPORTANT — ZERO-QUANTITY RULE: an Inventory row represents
    CURRENT physical stock. Once a stock-changing operation brings a
    row's quantity down to exactly 0, that row is deleted (handled
    in services.py, not here — this model doesn't enforce it itself
    since Django model-level hooks are the wrong layer for a rule
    that depends on which operation is running). The permanent
    history of that stock reaching zero lives in AuditLog, which is
    intentionally independent of this row's lifetime.

    The (product, location) pair can only appear once.

    PROTECT on both FKs: you cannot delete a Product or a Location
    while an Inventory row still references it.
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
    rejects it.

    Per the confirmed business rule, this targets EXISTING physical
    stock positions only — services.py enforces that an Inventory
    row already exists for (product, location) before this request
    can even be created, and again before it can be approved.
    """

    class Status(models.TextChoices):
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

    product_sku and location_info are plain text SNAPSHOTS, not
    ForeignKeys — deliberate, straight from the ER schema. An audit
    record should keep showing exactly what the SKU / location
    looked like at the moment the transaction happened, even after
    the corresponding Inventory row is later deleted under the
    zero-quantity rule, or if the real Product/Location record
    changes. Don't "fix" these into ForeignKeys without discussing
    it first — that would quietly break the audit trail's purpose.

    FLAGGED CONFLICT (unchanged from last session, still unresolved):
    The ER doc states `delete: restrict` for AuditLog.user_id
    (implemented below as PROTECT). An earlier session note claimed
    SET NULL instead. Still needs your confirmation — not part of
    this round of changes.
    """

    class ActionType(models.TextChoices):
        INBOUND = "INBOUND", "Inbound"
        OUTBOUND = "OUTBOUND", "Outbound"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    timestamp = models.DateTimeField(auto_now_add=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="audit_logs"
    )

    action_type = models.CharField(max_length=10, choices=ActionType.choices)
    product_sku = models.CharField(max_length=50)
    location_info = models.CharField(
        max_length=100, help_text="Snapshot string, e.g. 'A-R01-B01'."
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