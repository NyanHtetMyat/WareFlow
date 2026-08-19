"""
accounts/forms.py
────────────────────────────────────────────────────────────────
Handles user input validation for authentication-related forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm


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