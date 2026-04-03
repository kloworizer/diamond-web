from django import forms
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.status_data import StatusData

class JenisDataILAPForm(forms.ModelForm):
    class Meta:
        model = JenisDataILAP
        fields = [
            'id_ilap',
            'id_jenis_data',
            'nama_jenis_data',
            'id_sub_jenis_data',
            'nama_sub_jenis_data',
            'id_jenis_tabel',
            'id_status_data'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes for better styling
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

class JenisDataILAPUpdateForm(forms.ModelForm):
    """Form for updating existing JenisDataILAP - only allows editing nama_jenis_data and nama_sub_jenis_data"""
    class Meta:
        model = JenisDataILAP
        fields = [
            'nama_jenis_data',
            'nama_sub_jenis_data',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes for better styling
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'