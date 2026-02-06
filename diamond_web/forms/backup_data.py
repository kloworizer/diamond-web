from django import forms
from ..models.backup_data import BackupData
from ..models.tiket import Tiket

class BackupDataForm(forms.ModelForm):
    class Meta:
        model = BackupData
        fields = ['id_tiket', 'lokasi_backup']
        widgets = {
            'id_tiket': forms.Select(attrs={
                'class': 'form-select',
                'data-placeholder': 'Pilih Tiket'
            }),
            'lokasi_backup': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: /mnt/backup/tiket_123.zip atau Google Drive Link'
            }),
        }

    def __init__(self, *args, **kwargs):
        tiket_pk = kwargs.pop('tiket_pk', None)
        super().__init__(*args, **kwargs)
        
        # If tiket_pk is provided, remove the tiket field and set it from the view
        if tiket_pk:
            self.tiket_pk = tiket_pk
            # Remove the id_tiket field since it's determined by tiket_pk
            del self.fields['id_tiket']
        else:
            # Menampilkan nomor tiket dan status dalam dropdown
            self.fields['id_tiket'].queryset = Tiket.objects.all().order_by('-id')
            self.fields['id_tiket'].label_from_instance = lambda obj: f"{obj.nomor_tiket} (Status: {obj.status})" if obj.nomor_tiket else f"Tiket #{obj.id}"

    def clean(self):
        cleaned_data = super().clean()
        # If tiket_pk was provided, set it before returning
        if hasattr(self, 'tiket_pk'):
            try:
                cleaned_data['id_tiket'] = Tiket.objects.get(pk=self.tiket_pk)
            except Tiket.DoesNotExist:
                pass
        return cleaned_data
