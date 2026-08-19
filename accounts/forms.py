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
            'class': 'form-control',
            'placeholder': 'Username',
            'autofocus': True,
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
        })
    )