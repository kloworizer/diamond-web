from django import forms
from ..models.tiket import Tiket


class RekamHasilPenelitianForm(forms.ModelForm):
    """Form for recording research results."""
    catatan = forms.CharField(
        label='Catatan',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Masukkan catatan tambahan',
            'rows': 4
        }),
        required=True
    )
    
    class Meta:
        model = Tiket
        fields = ['baris_p3de']
        labels = {
            'baris_p3de': 'Baris P3DE'
        }
        widgets = {
            'baris_p3de': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan jumlah baris P3DE',
                'required': True
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['baris_p3de'].required = True
        if not self.fields['catatan'].initial:
            default_catatan = 'Hasil penelitian diubah' if self.instance and self.instance.tgl_teliti else 'Hasil penelitian direkam'
            self.fields['catatan'].initial = default_catatan

