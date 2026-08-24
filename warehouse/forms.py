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
    Staff-facing form for logging inbound stock.

    Product choices intentionally include EVERY product in the
    catalog, including ones with no Inventory yet — receiving is the
    operation that creates a product's first Inventory row.
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
    Staff-facing form for logging outbound stock. Product queryset
    restricted in __init__ (not as a class-level default) so it's
    refetched fresh on every request rather than once at startup.
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
    Staff-facing form for requesting a stock correction. Same
    Product-choice restriction as DispatchGoodsForm.
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