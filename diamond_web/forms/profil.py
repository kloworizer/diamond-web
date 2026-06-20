from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class ProfilForm(forms.ModelForm):
    """Form for updating user profile (first_name, last_name) and password."""

    old_password = forms.CharField(
        label="Old Password",
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
        required=False,
        help_text="Enter your current password to change it.",
    )
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False,
        help_text=(
            "Your password must contain at least 8 characters, "
            "can't be too similar to your personal info, "
            "can't be a commonly used password, and can't be entirely numeric."
        ),
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False,
        help_text="Enter the same password as above, for verification.",
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name']
        labels = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name

    def clean_old_password(self):
        """Validate that old_password matches the current user's password
        only if a new password is being set."""
        old_password = self.cleaned_data.get('old_password')
        new_password1 = self.cleaned_data.get('new_password1')

        if new_password1 and not old_password:
            raise ValidationError(
                "You must enter your current password to set a new one."
            )

        if old_password and self.user and not self.user.check_password(old_password):
            raise ValidationError(
                "Your current password is incorrect."
            )
        return old_password

    def clean_new_password1(self):
        """Validate the new password using Django's password validators."""
        new_password1 = self.cleaned_data.get('new_password1')
        if new_password1:
            validate_password(new_password1, user=self.user)
        return new_password1

    def clean_new_password2(self):
        """Ensure the two new password fields match."""
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')

        if new_password1 or new_password2:
            if new_password1 != new_password2:
                raise ValidationError("The two password fields didn't match.")
        return new_password2

    def save(self, commit=True):
        """Save profile changes and password if provided."""
        user = super().save(commit=False)

        # Update first_name and last_name
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        new_password = self.cleaned_data.get('new_password1')
        if new_password:
            user.set_password(new_password)

        if commit:
            user.save()

        return user
