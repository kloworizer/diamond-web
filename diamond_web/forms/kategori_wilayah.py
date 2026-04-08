from django import forms
from ..models.kategori_wilayah import KategoriWilayah
from .base import AutoRequiredFormMixin

class KategoriWilayahForm(AutoRequiredFormMixin, forms.ModelForm):
    class Meta:
        model = KategoriWilayah
        fields = ['deskripsi']
