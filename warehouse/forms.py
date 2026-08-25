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
from .models import Category, Location, Product, Supplier


class ReceiveGoodsForm(forms.Form):
    """
    Product and Location are now hidden fields — the visible
    searchable Product combobox and Zone->Rack->Bin cascade
    (static/js/location_cascade.js) write into these directly.
    Django-level validation is unchanged: still a real
    ModelChoiceField, still rejects an invalid/tampered id.
    """
    product = forms.ModelChoiceField(
        queryset=Product.objects.select_related('supplier').all(),
        widget=forms.HiddenInput(attrs={'id': 'id_product'}),
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        widget=forms.HiddenInput(attrs={'id': 'id_location'}),
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
    """Product-first cascade — see location_cascade.js's productFirst mode."""
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        widget=forms.HiddenInput(attrs={'id': 'id_product'}),
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        widget=forms.HiddenInput(attrs={'id': 'id_location'}),
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
    product/location querysets stay intentionally broad
    (Product.objects.all() / Location.objects.all()) regardless of
    Increase/Decrease mode — the frontend combobox only OFFERS the
    mode-appropriate subset, but Django must still accept whichever
    of the two subsets was actually shown. The authoritative
    per-mode rule (does this pair have existing inventory?) is
    enforced in services.submit_adjustment_request(), not here.
    """
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        widget=forms.HiddenInput(attrs={'id': 'id_product'}),
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        widget=forms.HiddenInput(attrs={'id': 'id_location'}),
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

    def clean_quantity_change(self):
        value = self.cleaned_data['quantity_change']
        if value == 0:
            raise forms.ValidationError("Quantity change cannot be zero.")
        return value


class ProductForm(forms.ModelForm):
    """Manager-facing form for creating/editing a Product."""

    class Meta:
        model = Product
        fields = ['sku', 'name', 'category', 'supplier', 'low_stock_threshold']
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


class SupplierForm(forms.ModelForm):
    """Manager-facing form for creating/editing a Supplier."""

    class Meta:
        model = Supplier
        fields = ['name', 'contact_info']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_info': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class CategoryForm(forms.ModelForm):
    """Manager-facing form for creating/editing a Category."""

    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class LocationForm(forms.ModelForm):
    """
    Manager-facing form for creating/editing a Location.

    Zone's uppercase-only validation and rack/bin's positive-integer
    validation both live on the model itself (see Location.save()
    and the field validators in models.py) — this form doesn't
    duplicate that logic, it just supplies the widgets. Django's
    ModelForm automatically surfaces the model's own
    UniqueConstraint on (zone, rack, bin) as a form error if a
    duplicate is submitted.
    """

    class Meta:
        model = Location
        fields = ['zone', 'rack', 'bin']
        widgets = {
            'zone': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 10, 'placeholder': 'e.g. A'}),
            'rack': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'bin': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }