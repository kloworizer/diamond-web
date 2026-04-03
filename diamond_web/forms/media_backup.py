from django import forms
from ..models.media_backup import MediaBackup

class MediaBackupForm(forms.ModelForm):
    class Meta:
        model = MediaBackup
        fields = ['deskripsi']
