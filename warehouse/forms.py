"""
warehouse/forms.py
────────────────────────────────────────────────────────────────
Input validation for warehouse workflows. Forms validate SHAPE
(is this a real Product, is quantity a positive number) — the
business rule of whether that quantity is actually achievable
(enough stock on hand, etc.) lives in services.py, not here.
"""

from django import forms
from django.utils import timezone

from .models import Location, Product


class LocationChoiceField(forms.ModelChoiceField):
    """
    Displays each location as "Zone A · Rack 14 · Bin 05" instead of
    Django's default string representation, so Staff can identify the
    exact bin directly from the dropdown without a separate lookup.
    """
    def label_from_instance(self, location):
        return f"{location.zone} · {location.rack} · {location.bin}"


class ReceiveGoodsForm(forms.Form):
    """
    Staff-facing form for logging inbound stock.

    The product dropdown is rendered manually in the template (not via
    {{ form.product }}) so each <option> can carry a data-supplier
    value — this drives the read-only Supplier field auto-filling in
    the UI via static/js/forms.js, with no extra backend call needed.
    select_related('supplier') avoids a separate query per product
    when the template loop reads product.supplier.name.
    """

    product = forms.ModelChoiceField(
        queryset=Product.objects.select_related('supplier').all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    location = LocationChoiceField(
        queryset=Location.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )

    # Display-only: always shows today's date and ignores any submitted
    # value (Django enforces this automatically for disabled fields).
    # The real, trustworthy timestamp is set server-side using the
    # server clock when services.receive_goods() runs — never taken
    # from client input, since a client-supplied date can't be trusted
    # for an audit record.
    date = forms.DateField(
        disabled=True,
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={'class': 'form-control'}),
    )


class DispatchGoodsForm(forms.Form):
    """
    Staff-facing form for logging outbound stock. Same shape as
    ReceiveGoodsForm, minus the supplier auto-fill — Dispatch has no
    Supplier field at all, per the confirmed requirement.
    """

    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    location = LocationChoiceField(
        queryset=Location.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
    date = forms.DateField(
        disabled=True,
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={'class': 'form-control'}),
    )