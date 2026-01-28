from django import forms
from ..models.kategori_wilayah import KategoriWilayah

class KategoriWilayahForm(forms.ModelForm):
    class Meta:
        model = KategoriWilayah
        fields = ['deskripsi']
