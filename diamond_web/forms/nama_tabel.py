from collections import OrderedDict
from django import forms
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.nama_tabel_jenis_data import NamaTabelJenisData
from .base import AutoRequiredFormMixin


class NamaTabelForm(AutoRequiredFormMixin, forms.ModelForm):
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

    def clean(self):
        """Reject a name the sub jenis data already carries as a second table.

        The pair is unique per jenis data, so without this the save would come
        back as an IntegrityError instead of a message on the field.
        """
        cleaned = super().clean()
        sub = cleaned.get('sub_jenis') or self.instance
        nama_i = cleaned.get('nama_tabel_I')
        if sub and sub.pk and nama_i:
            bentrok = NamaTabelJenisData.objects.filter(
                id_jenis_data_ilap=sub, nama_tabel_I=nama_i, utama=False
            ).exists()
            if bentrok:
                self.add_error(
                    'nama_tabel_I',
                    'Nama tabel ini sudah terdaftar pada sub jenis data tersebut.',
                )
        return cleaned

    def save(self, commit=True):
        """Write the table name to its own row, not to the jenis data.

        The names live in `NamaTabelJenisData`; `JenisDataILAP` keeps only the
        utama one, as a cache that `sync_nama_tabel_cache_on_save` rewrites.
        Assigning the jenis data's fields here would be overwritten by that
        signal anyway, so the child row is the whole save.

        `sub_jenis` is present on the create form and absent on the update
        form, where the instance being edited is the jenis data itself.
        """
        sub = self.cleaned_data.get('sub_jenis') or self.instance
        if not commit:
            return sub

        nama_i = self.cleaned_data.get('nama_tabel_I', '')
        nama_u = self.cleaned_data.get('nama_tabel_U', '')
        utama = NamaTabelJenisData.objects.filter(
            id_jenis_data_ilap=sub, utama=True
        ).first()
        if utama is None:
            NamaTabelJenisData.objects.create(
                id_jenis_data_ilap=sub,
                nama_tabel_I=nama_i,
                nama_tabel_U=nama_u,
                utama=True,
                aktif=True,
            )
        else:
            utama.nama_tabel_I = nama_i
            utama.nama_tabel_U = nama_u
            utama.save(update_fields=['nama_tabel_I', 'nama_tabel_U'])

        sub.refresh_from_db(fields=['nama_tabel_I', 'nama_tabel_U'])
        return sub
