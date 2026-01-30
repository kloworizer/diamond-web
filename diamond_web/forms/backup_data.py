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
        super().__init__(*args, **kwargs)
        # Menampilkan nomor tiket dan status dalam dropdown
        self.fields['id_tiket'].queryset = Tiket.objects.all().order_by('-id')
        self.fields['id_tiket'].label_from_instance = lambda obj: f"{obj.nomor_tiket} (Status: {obj.status})" if obj.nomor_tiket else f"Tiket #{obj.id}"
