from django import forms
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.status_data import StatusData
from .base import AutoRequiredFormMixin

class JenisDataILAPForm(AutoRequiredFormMixin, forms.ModelForm):
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

class JenisDataILAPUpdateForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form for updating an existing JenisDataILAP.

    The identifiers stay out of the form: ILAP, id jenis data and id sub jenis
    data are the keys the rest of the data hangs off, and the create wizard is
    what derives them. What is editable is everything descriptive — the two
    names, plus the jenis tabel and status data lookups, which are corrections
    made after the row exists rather than facts fixed at creation.
    """
    class Meta:
        model = JenisDataILAP
        fields = [
            'nama_jenis_data',
            'nama_sub_jenis_data',
            'id_jenis_tabel',
            'id_status_data',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes for better styling
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'