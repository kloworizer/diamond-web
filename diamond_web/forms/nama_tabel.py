from collections import OrderedDict
from django import forms
from ..models.jenis_data_ilap import JenisDataILAP


class NamaTabelForm(forms.ModelForm):
    # A selector for choosing an existing `JenisDataILAP` (sub-jenis) to
    # assign table names to. This is only shown on the create form; the
    # update form edits an existing instance directly.
    sub_jenis = forms.ModelChoiceField(
        queryset=JenisDataILAP.objects.none(),
        required=True,
        label="Sub Jenis Data",
    )

    class Meta:
        model = JenisDataILAP
        fields = ['nama_tabel_I', 'nama_tabel_U']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If this form is bound to an existing instance (UpdateView), hide
        # the `sub_jenis` selector — editing operates on the instance.
        if getattr(self, 'instance', None) and getattr(self.instance, 'pk', None):
            self.fields.pop('sub_jenis', None)
        else:
            # For create form, offer only those sub-jenis that do not yet
            # have table names assigned (both I and U empty).
            qs = JenisDataILAP.objects.filter(nama_tabel_I='').filter(nama_tabel_U='')
            self.fields['sub_jenis'].queryset = qs

        for field_name, field in self.fields.items():
            # Ensure consistent bootstrap styling for widgets
            field.widget.attrs.update({'class': 'form-control'})

        # If we have the `sub_jenis` selector (create form), move it to the
        # top so it appears first in the modal/form.
        if 'sub_jenis' in self.fields:
            sub_field = self.fields.pop('sub_jenis')
            # Rebuild ordered dict with sub_jenis first
            new_fields = OrderedDict([('sub_jenis', sub_field)])
            new_fields.update(self.fields)
            self.fields = new_fields

    def save(self, commit=True):
        # If the form includes `sub_jenis`, the intent is to update an
        # existing `JenisDataILAP` instance rather than create a new one.
        sub = self.cleaned_data.get('sub_jenis') if 'sub_jenis' in self.cleaned_data else None
        if sub is not None:
            sub.nama_tabel_I = self.cleaned_data.get('nama_tabel_I', '')
            sub.nama_tabel_U = self.cleaned_data.get('nama_tabel_U', '')
            if commit:
                sub.save()
            return sub
        return super().save(commit=commit)
