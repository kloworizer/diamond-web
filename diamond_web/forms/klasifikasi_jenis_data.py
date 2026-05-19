from django import forms
from ..models.klasifikasi_jenis_data import KlasifikasiJenisData
from .base import AutoRequiredFormMixin

class KlasifikasiJenisDataForm(AutoRequiredFormMixin, forms.ModelForm):
    class Meta:
        model = KlasifikasiJenisData
        fields = [
            'id_sub_jenis_data',
            'id_klasifikasi_tabel'
        ]
