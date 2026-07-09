from django import forms
from ..models.klasifikasi_jenis_data import KlasifikasiJenisData
from ..models.jenis_data_ilap import JenisDataILAP
from .base import AutoRequiredFormMixin

class KlasifikasiJenisDataForm(AutoRequiredFormMixin, forms.ModelForm):
    class Meta:
        model = KlasifikasiJenisData
        fields = [
            'id_sub_jenis_data',
            'id_klasifikasi_tabel'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order dropdown by id_sub_jenis_data (e.g., AS0010101, AS0010102)
        # instead of the default ordering by auto-increment id
        self.fields['id_sub_jenis_data'].queryset = JenisDataILAP.objects.all().order_by('id_sub_jenis_data')
