from django import forms
from ..models.jenis_data_ilap import JenisDataILAP

class JenisDataILAPForm(forms.ModelForm):
    class Meta:
        model = JenisDataILAP
        fields = [
            'id_kategori_ilap',
            'id_ilap',
            'id_jenis_data',
            'nama_jenis_data',
            'id_sub_jenis_data',
            'nama_sub_jenis_data',
            'id_jenis_tabel',
            'id_klasifikasi_tabel'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes for better styling
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
