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


class ForgotPasswordForm(forms.Form):
    """
    Public "I forgot my password" form. Deliberately a plain Form,
    not a ModelForm — it never creates or edits a User directly.
    accounts.services.submit_password_reset_request does the actual
    lookup (by username OR email) and PasswordResetRequest creation,
    and deliberately never raises a validation error for "no match
    found" — see that function's docstring for why.
    """
    identifier = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(attrs={
            'class': 'form-control auth-field',
            'placeholder': 'Username or Email',
            'autofocus': True,
        })
    )


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

    def clean_role(self):
        """
        Role changes through this form are restricted to STAFF <->
        MANAGER only. An existing ADMIN can never be demoted, and a
        STAFF/MANAGER can never be promoted to ADMIN — checked here
        against self.instance.role (the value BEFORE this edit),
        so this holds even if a manually crafted POST request omits
        or tampers with the Role field's disabled <option> elements
        in the UI, which are cosmetic only.
        """
        new_role = self.cleaned_data['role']
        original_role = self.instance.role

        if original_role == User.Role.ADMIN and new_role != User.Role.ADMIN:
            raise forms.ValidationError("Admin accounts cannot be demoted.")
        if original_role != User.Role.ADMIN and new_role == User.Role.ADMIN:
            raise forms.ValidationError("Users cannot be promoted to Admin.")

        return new_role


class AdminUserCreateForm(forms.ModelForm):
    """
    Admin-facing form for creating a brand new Staff or Manager
    account. Deliberately reuses the exact same Meta.fields shape as
    AdminUserEditForm (email/first_name/last_name/role) plus
    'username', which IS required here since it's how the new
    account is identified.

    No password field exists on this form on purpose — every new
    account is created with settings.DEFAULT_RESET_PASSWORD (see
    accounts.views.user_create), the same fixed system default
    already used by the existing "Reset Password" action. The user
    is expected to set their own password afterward via My Profile.

    Per WareFlow Project Structure v.2, Section 10, Admin account
    creation through this form is scoped to Staff and Manager only
    — Role choices are narrowed in __init__ rather than in Meta so
    AdminUserEditForm's full three-role dropdown is unaffected.
    """

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [
            (User.Role.STAFF, User.Role.STAFF.label),
            (User.Role.MANAGER, User.Role.MANAGER.label),
        ]