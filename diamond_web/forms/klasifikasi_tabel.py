from django import forms
from ..models.klasifikasi_tabel import KlasifikasiTabel

class KlasifikasiTabelForm(forms.ModelForm):
    class Meta:
        model = KlasifikasiTabel
        fields = ['deskripsi']
