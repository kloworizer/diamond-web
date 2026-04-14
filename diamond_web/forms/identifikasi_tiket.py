from django import forms
from ..models.tiket import Tiket
from ..utils import validate_not_future_datetime


class IdentifikasiTiketForm(forms.ModelForm):
    """Form for PIDE to mark tiket as identified and record tgl_rekam_pide."""
    
    class Meta:
        model = Tiket
        fields = ['tgl_rekam_pide']
        widgets = {
            'tgl_rekam_pide': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'required': 'required',
            }),
        }
        labels = {
            'tgl_rekam_pide': 'Tanggal Rekam PIDE',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set tgl_rekam_pide as required
        self.fields['tgl_rekam_pide'].required = True
        self.fields['tgl_rekam_pide'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']

        # Pre-format tgl_rekam_pide for datetime-local input
        if self.instance and self.instance.tgl_rekam_pide:
            self.initial['tgl_rekam_pide'] = self.instance.tgl_rekam_pide.strftime('%Y-%m-%dT%H:%M')

    def clean_tgl_rekam_pide(self):
        value = self.cleaned_data.get('tgl_rekam_pide')
        return validate_not_future_datetime(value, "Tanggal Rekam PIDE")
