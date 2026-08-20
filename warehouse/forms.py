"""
warehouse/forms.py
────────────────────────────────────────────────────────────────
Input validation for warehouse workflows. Forms validate SHAPE
(is this a real Product, is quantity a positive number) — the
business rule of whether that quantity is actually achievable
lives in services.py, not here.
"""

from django import forms
from django.utils import timezone

from . import services
from .models import Location, Product


class ReceiveGoodsForm(forms.Form):
    """
    Staff-facing form for logging inbound stock.

    Product choices intentionally include EVERY product in the
    catalog, including ones with no Inventory yet — receiving is the
    operation that creates a product's first Inventory row, so
    restricting this dropdown would make it impossible to ever
    receive a brand-new product. Location choices are similarly
    unrestricted: any valid warehouse location is a legal place to
    receive goods into.
    """

    product = forms.ModelChoiceField(
        queryset=Product.objects.select_related('supplier').all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    location = forms.ModelChoiceField(
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


class DispatchGoodsForm(forms.Form):
    """
    Staff-facing form for logging outbound stock.

    Unlike Receive, Dispatch must only ever target Product+Location
    combinations that currently hold physical stock — the Product
    queryset is restricted in __init__ below (not as a class-level
    default, so it's re-fetched fresh on every request rather than
    once at server startup). The Location field's queryset stays
    broad at the Django level; the authoritative Product+Location
    PAIR check happens in services.dispatch_goods(), exactly as the
    business rules require — UI filtering (via inventory_chain.js)
    is for user experience, the backend re-checks regardless.
    """

    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    location = forms.ModelChoiceField(
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = services.get_stocked_products()


class StockAdjustmentRequestForm(forms.Form):
    """
    Staff-facing form for requesting a stock correction.

    Same Product-choice restriction as DispatchGoodsForm and for the
    same reason: an adjustment corrects EXISTING physical stock, it
    is not a disguised way to receive a brand-new product.
    """

    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quantity_change = forms.IntegerField(
        widget=forms.HiddenInput(attrs={'id': 'id_quantity_change'}),
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'maxlength': 500,
            'placeholder': 'Explain the discrepancy — e.g. "Damaged in transit, 3 units unsellable."',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = services.get_stocked_products()

    def clean_quantity_change(self):
        value = self.cleaned_data['quantity_change']
        if value == 0:
            raise forms.ValidationError("Quantity change cannot be zero.")
        return value