from django import forms
from ..models.tiket import Tiket


class DikembalikanTiketForm(forms.ModelForm):
    """Form for returning a tiket (Dikembalikan) by PIDE."""
    catatan = forms.CharField(
        label='Catatan',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Masukkan alasan pengembalian tiket',
            'rows': 4
        }),
        required=True
    )

    class Meta:
        model = Tiket
        fields = []
