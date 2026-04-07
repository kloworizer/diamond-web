from django import forms
from ..models.media_backup import MediaBackup
from .base import AutoRequiredFormMixin

class MediaBackupForm(AutoRequiredFormMixin, forms.ModelForm):
    class Meta:
        model = MediaBackup
        fields = ['deskripsi']
