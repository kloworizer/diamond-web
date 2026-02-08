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
        user = kwargs.pop('user', None)
        tiket_pk = kwargs.pop('tiket_pk', None)
        super().__init__(*args, **kwargs)

        # If tiket_pk is provided, remove the tiket field and set it from the view
        if tiket_pk:
            self.tiket_pk = tiket_pk
            # Remove the id_tiket field since it's determined by tiket_pk
            del self.fields['id_tiket']
        else:
            # Only show tickets where user is active PIC P3DE and status < 8
            from ..models.tiket_pic import TiketPIC
            if user is not None:
                tiket_ids = TiketPIC.objects.filter(
                    id_user=user,
                    role=TiketPIC.Role.P3DE,
                    active=True
                ).values_list('id_tiket_id', flat=True)
                self.fields['id_tiket'].queryset = Tiket.objects.filter(id__in=tiket_ids, status__lt=4).order_by('-id')
            else:
                self.fields['id_tiket'].queryset = Tiket.objects.none()
            self.fields['id_tiket'].label_from_instance = lambda obj: obj.nomor_tiket if obj.nomor_tiket else f"Tiket #{obj.id}"
            # If editing (instance exists), set queryset to only the current tiket, set initial, and disable
            if self.instance and self.instance.pk:
                self.fields['id_tiket'].queryset = Tiket.objects.filter(pk=self.instance.id_tiket_id)
                self.fields['id_tiket'].initial = self.instance.id_tiket_id
                self.fields['id_tiket'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        # If editing (instance exists), remove id_tiket from cleaned_data to avoid validation error
        if self.instance and self.instance.pk:
            cleaned_data.pop('id_tiket', None)
        # If tiket_pk was provided (create from tiket), set it before returning
        elif hasattr(self, 'tiket_pk'):
            try:
                cleaned_data['id_tiket'] = Tiket.objects.get(pk=self.tiket_pk)
            except Tiket.DoesNotExist:
                pass
        return cleaned_data
