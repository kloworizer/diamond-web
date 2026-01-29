from django import forms
from ..models.tiket import Tiket


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
        required=True,
        help_text="Comma-separated list of tiket IDs"
    )

    def clean_tiket_ids(self):
        """Validate that tiket_ids is not empty and contains valid IDs."""
        tiket_ids = self.cleaned_data.get('tiket_ids', '')
        if not tiket_ids:
            raise forms.ValidationError("Please select at least one tiket.")
        
        try:
            ids = [int(id.strip()) for id in tiket_ids.split(',') if id.strip()]
        except ValueError:
            raise forms.ValidationError("Invalid tiket IDs provided.")
        
        if not ids:
            raise forms.ValidationError("Please select at least one tiket.")
        
        # Check if all tiket IDs exist
        existing_tikets = Tiket.objects.filter(id__in=ids).values_list('id', flat=True)
        if len(existing_tikets) != len(ids):
            raise forms.ValidationError("Some tiket IDs do not exist.")
        
        return tiket_ids
