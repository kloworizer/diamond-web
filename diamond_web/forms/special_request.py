from django import forms
from ..models.tiket import Tiket
from .base import AutoRequiredFormMixin
from ..utils import end_of_day

# Shared by every form that exposes the special request switch: the due date
# is mandatory as soon as the switch is on.
DUE_DATE_REQUIRED_ERROR = (
    'Tanggal Jatuh Tempo wajib diisi ketika Permintaan Khusus diaktifkan.'
)


class SpecialRequestForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form for toggling the Special Request flag of a tiket by P3DE/PIDE."""
    special_request = forms.BooleanField(
        label='Permintaan Khusus',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'role': 'switch',
        }),
        required=False
    )
    tgl_special_request = forms.DateTimeField(
        label='Jatuh Tempo Permintaan Khusus',
        widget=forms.DateInput(
            attrs={'type': 'date', 'class': 'form-control'},
            format='%Y-%m-%d',
        ),
        required=False
    )
    catatan = forms.CharField(
        label='Catatan',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Masukkan catatan perubahan permintaan khusus (opsional)',
            'rows': 3
        }),
        required=False
    )

    class Meta:
        model = Tiket
        fields = ['special_request', 'tgl_special_request']

    def clean_tgl_special_request(self):
        """Store the due date at the end of the selected day."""
        return end_of_day(self.cleaned_data.get('tgl_special_request'))

    def clean(self):
        """Tie the due date to the flag: mandatory when on, dropped when off."""
        cleaned_data = super().clean()
        if cleaned_data.get('special_request'):
            if not cleaned_data.get('tgl_special_request'):
                self.add_error('tgl_special_request', DUE_DATE_REQUIRED_ERROR)
        else:
            cleaned_data['tgl_special_request'] = None
        return cleaned_data
