from django import forms
from ..models.klasifikasi_jenis_data import KlasifikasiJenisData

class KlasifikasiJenisDataForm(forms.ModelForm):
    class Meta:
        model = KlasifikasiJenisData
        fields = [
            'id_jenis_data_ilap',
            'id_klasifikasi_tabel'
        ]
