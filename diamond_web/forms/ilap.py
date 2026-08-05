from django import forms
from ..models.ilap import ILAP
from ..models.ilap_kpp import ILAPKPP
from ..models.kanwil import Kanwil
from ..models.kpp import KPP
from .base import AutoRequiredFormMixin

# Kategori of a Regional ILAP decides which wilayah it is mapped to: PD
# (Pemerintah Daerah Kabupaten/Kota) maps to a KPP, PV (Pemerintah Daerah
# Provinsi) has no KPP counterpart and maps straight to a Kanwil.
KATEGORI_KPP = 'PD'
KATEGORI_KANWIL = 'PV'


class KategoriChoiceField(forms.ModelChoiceField):
    """Custom ModelChoiceField that uses id_kategori as the value instead of pk."""
    def to_python(self, value):
        if value in self.empty_values:
            return None
        # If value is already a model instance (e.g. when field is disabled), return as-is
        if isinstance(value, self.queryset.model):
            return value
        try:
            # Try to get by id_kategori first
            return self.queryset.get(id_kategori=value)
        except (ValueError, TypeError, self.queryset.model.DoesNotExist):
            # Fall back to pk for compatibility
            return self.queryset.get(pk=value)
    
    def prepare_value(self, value):
        if value is None:
            return ''
        if hasattr(value, 'id_kategori'):
            return value.id_kategori
        return value


class ILAPForm(AutoRequiredFormMixin, forms.ModelForm):
    id_kategori = KategoriChoiceField(queryset=None)
    kpp_list = forms.ModelMultipleChoiceField(
        queryset=KPP.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="KPP",
        help_text="Pilih satu atau lebih KPP yang terkait dengan ILAP ini."
    )
    kanwil_list = forms.ModelMultipleChoiceField(
        queryset=Kanwil.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Kanwil",
        help_text="Pilih satu atau lebih Kanwil yang terkait dengan ILAP ini."
    )

    class Meta:
        model = ILAP
        fields = [
            'id_kategori', 'id_ilap', 'nama_ilap', 'id_kategori_wilayah',
            'alamat_ilap', 'kota_ilap', 'namapic_ilap', 'jabatan_picilap',
            'telp_kantor', 'fax_ilap', 'email_picilap', 'telp_pic',
            'tujuan_surat', 'tembusan',
        ]
        widgets = {
            'id_ilap': forms.TextInput(attrs={'readonly': 'readonly'}),
            'alamat_ilap': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the queryset for the custom field
        from ..models.kategori_ilap import KategoriILAP
        self.fields['id_kategori'].queryset = KategoriILAP.objects.all()
        
        # Always make id_ilap readonly visually
        self.fields['id_ilap'].widget.attrs['readonly'] = 'readonly'
        self.fields['id_ilap'].widget.attrs['class'] = 'form-control'
        self.fields['id_ilap'].required = False
        
        # Pre-populate the wilayah checkboxes with existing ILAPKPP relations
        # when editing. Rows are split on the side that is actually filled
        # rather than on the `kpp` flag, so legacy rows carrying the default
        # flag still land in the right list.
        if self.instance.pk:
            relations = self.instance.ilap_kpp_relations.all()
            self.initial['kpp_list'] = [rel.id_kpp_id for rel in relations if rel.id_kpp_id]
            self.initial['kanwil_list'] = [rel.id_kanwil_id for rel in relations if rel.id_kanwil_id]
            # In edit mode, disable both id_ilap and id_kategori
            self.fields['id_ilap'].disabled = True
            self.fields['id_kategori'].disabled = True
            
            # Set id_kategori initial value as string (id_kategori field value, not PK)
            # so the select widget can match it against option values
            kategori = getattr(self.instance, 'id_kategori', None)
            if kategori:
                self.initial['id_kategori'] = kategori.id_kategori
    
    @staticmethod
    def maps_to_kanwil(kategori):
        """Return True when this kategori is mapped to a Kanwil instead of a KPP."""
        return getattr(kategori, 'id_kategori', '') == KATEGORI_KANWIL

    def _wilayah_mode(self):
        """Return which wilayah side applies to the submitted data.

        Returns one of ``'kpp'``, ``'kanwil'`` or ``None`` — the latter when
        kategori_wilayah is not Regional and no wilayah may be attached.
        """
        kategori_wilayah = self.cleaned_data.get('id_kategori_wilayah')
        if not (kategori_wilayah and 'regional' in str(kategori_wilayah).lower()):
            return None
        return 'kanwil' if self.maps_to_kanwil(self.cleaned_data.get('id_kategori')) else 'kpp'

    def clean(self):
        """Keep only the wilayah selection that matches kategori and wilayah.

        A Regional ILAP of kategori PD selects KPP, one of kategori PV selects
        Kanwil, and a non-Regional ILAP selects neither. Selections on the side
        that does not apply are dropped rather than rejected, so switching
        kategori_wilayah in the form never blocks the save.
        """
        cleaned_data = super().clean()
        mode = self._wilayah_mode()

        if mode != 'kpp':
            cleaned_data['kpp_list'] = []
        if mode != 'kanwil':
            cleaned_data['kanwil_list'] = []

        return cleaned_data

    def save(self, commit=True):
        """Save ILAP instance and manage ILAPKPP relationships."""
        ilap = super().save(commit=commit)

        if commit:
            self._save_wilayah_relations(ilap)
        else:
            # If not committing, attach a callback for the caller to invoke
            self._pending_kpp_save = lambda: self._save_wilayah_relations(ilap)

        return ilap

    def _save_wilayah_relations(self, ilap):
        """Sync ILAPKPP rows to match the selected kpp_list / kanwil_list.

        `clean` has already emptied the side that does not apply, so a
        non-Regional ILAP ends up with every mapping row removed.
        """
        selected_kpp_ids = {kpp.pk for kpp in self.cleaned_data.get('kpp_list') or []}
        selected_kanwil_ids = {kanwil.pk for kanwil in self.cleaned_data.get('kanwil_list') or []}

        existing = list(ilap.ilap_kpp_relations.all())
        existing_kpp_ids = {rel.id_kpp_id for rel in existing if rel.id_kpp_id}
        existing_kanwil_ids = {rel.id_kanwil_id for rel in existing if rel.id_kanwil_id}

        # Drop rows that were deselected, plus any row pointing at nothing
        stale_ids = [
            rel.pk for rel in existing
            if (rel.id_kpp_id is None and rel.id_kanwil_id is None)
            or (rel.id_kpp_id and rel.id_kpp_id not in selected_kpp_ids)
            or (rel.id_kanwil_id and rel.id_kanwil_id not in selected_kanwil_ids)
        ]
        if stale_ids:
            ILAPKPP.objects.filter(pk__in=stale_ids).delete()

        # Create rows for newly selected KPP / Kanwil
        for kpp_pk in selected_kpp_ids - existing_kpp_ids:
            ILAPKPP.objects.create(id_ilap=ilap, kpp=True, id_kpp_id=kpp_pk)
        for kanwil_pk in selected_kanwil_ids - existing_kanwil_ids:
            ILAPKPP.objects.create(id_ilap=ilap, kpp=False, id_kanwil_id=kanwil_pk)
