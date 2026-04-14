from django import forms
from ..models.tiket import Tiket
from ..utils import validate_not_future_datetime


class KirimTiketForm(forms.Form):
    """Form for Kirim Tiket workflow step."""
    nomor_nd_nadine = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nomor ND Nadine'})
    )
    tgl_nadine = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )
    tgl_kirim_pide = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )
    tiket_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        help_text="Comma-separated list of tiket IDs"
    )

    def clean_tgl_nadine(self):
        value = self.cleaned_data.get('tgl_nadine')
        return validate_not_future_datetime(value, "Tanggal Nadine")

    def clean_tgl_kirim_pide(self):
        value = self.cleaned_data.get('tgl_kirim_pide')
        return validate_not_future_datetime(value, "Tanggal Kirim PIDE")

    def clean_tiket_ids(self):
        """Validate that tiket_ids is not empty and contains valid IDs."""
        tiket_ids = self.cleaned_data.get('tiket_ids', '')
        if not tiket_ids:
            # If only one tiket is available, allow empty (will be set in initial)
            if hasattr(self, 'initial') and self.initial.get('tiket_ids'):
                tiket_ids = self.initial['tiket_ids']
        if not tiket_ids:
            raise forms.ValidationError("Silakan pilih minimal satu tiket.")
        try:
            ids = [int(id.strip()) for id in tiket_ids.split(',') if id.strip()]
        except ValueError:
            raise forms.ValidationError("ID tiket tidak valid.")
        if not ids:
            raise forms.ValidationError("Silakan pilih minimal satu tiket.")
        # Check if all tiket IDs exist
        existing_tikets = Tiket.objects.filter(id__in=ids).values_list('id', flat=True)
        if len(existing_tikets) != len(ids):
            raise forms.ValidationError("Beberapa ID tiket tidak ditemukan.")
        return tiket_ids
