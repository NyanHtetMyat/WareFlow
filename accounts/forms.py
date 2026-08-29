"""
accounts/forms.py
────────────────────────────────────────────────────────────────
Handles user input validation for authentication-related forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from .models import User

class WareFlowLoginForm(AuthenticationForm):
    """
    Login form for WareFlow.

    Built on Django's AuthenticationForm so credential checking and
    error messages ("invalid username or password", "account
    inactive", etc.) keep working the way Django expects. Only the
    widget styling is customized here for a cleaner look.
    """

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            # "auth-field" strips the input's own border/background so
            # it sits invisibly inside the .auth-input-group capsule,
            # which owns the visible border and focus highlight instead.
            'class': 'form-control auth-field',
            'placeholder': 'Username',
            'autofocus': True,
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control auth-field',
            'placeholder': 'Password',
        })
    )


class ProfileForm(forms.ModelForm):
    """
    Own-profile edit form. ONLY first_name, last_name, and image are
    listed here — this is the actual backend enforcement that
    username/email/role can never be changed through this form,
    regardless of what a tampered POST request contains, since
    Django's ModelForm only ever writes fields present in Meta.fields.
    """

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'image']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
        }


class ChangePasswordForm(PasswordChangeForm):
    """
    Thin wrapper around Django's built-in PasswordChangeForm, adding
    only WareFlow's usual widget styling — the actual old-password
    verification and new-password validation logic is entirely
    Django's own, not reimplemented here.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})


class AdminUserEditForm(forms.ModelForm):
    """
    Admin-facing edit form for another user's account. Username is
    deliberately NOT listed here — per the confirmed requirement,
    it stays read-only unless a future need explicitly justifies
    changing it. Password is handled entirely separately (see
    accounts.views.user_reset_password), never inside this form.
    """

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'role']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
        }