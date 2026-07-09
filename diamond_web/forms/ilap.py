from django import forms
from ..models.ilap import ILAP
from ..models.ilap_kpp import ILAPKPP
from ..models.kpp import KPP
from .base import AutoRequiredFormMixin


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
        
        # Pre-populate kpp_list with existing ILAPKPP relations when editing
        if self.instance.pk:
            self.initial['kpp_list'] = (
                self.instance.ilap_kpp_relations.values_list('id_kpp', flat=True)
            )
            # In edit mode, disable both id_ilap and id_kategori
            self.fields['id_ilap'].disabled = True
            self.fields['id_kategori'].disabled = True
            
            # Set id_kategori initial value as string (id_kategori field value, not PK)
            # so the select widget can match it against option values
            kategori = getattr(self.instance, 'id_kategori', None)
            if kategori:
                self.initial['id_kategori'] = kategori.id_kategori
    
    def clean(self):
        """Validate that kpp_list is only set when kategori_wilayah is Regional."""
        cleaned_data = super().clean()
        kategori_wilayah = cleaned_data.get('id_kategori_wilayah')
        kpp_list = cleaned_data.get('kpp_list')
        
        is_regional = kategori_wilayah and 'regional' in str(kategori_wilayah).lower()
        
        if not is_regional and kpp_list:
            # Clear KPP selections if kategori_wilayah is not Regional
            cleaned_data['kpp_list'] = []
        elif is_regional and not kpp_list:
            # KPP is optional even for Regional ILAPs, so no error raised
            pass
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save ILAP instance and manage ILAPKPP relationships."""
        ilap = super().save(commit=commit)
        
        # Only save KPP relations if kategori_wilayah is Regional
        kategori_wilayah = self.cleaned_data.get('id_kategori_wilayah') or ilap.id_kategori_wilayah
        is_regional = kategori_wilayah and 'regional' in str(kategori_wilayah).lower()
        
        if commit and is_regional:
            self._save_kpp_relations(ilap)
        elif commit and not is_regional:
            # Remove all KPP relations if kategori_wilayah changed to non-Regional
            ILAPKPP.objects.filter(id_ilap=ilap).delete()
        elif not commit:
            # If not committing, attach a callback for the caller to invoke
            self._pending_kpp_save = lambda: (
                self._save_kpp_relations(ilap) if is_regional
                else ILAPKPP.objects.filter(id_ilap=ilap).delete()
            )
        
        return ilap
    
    def _save_kpp_relations(self, ilap):
        """Sync ILAPKPP relations to match the selected kpp_list."""
        selected_kpp_ids = {kpp.pk for kpp in self.cleaned_data.get('kpp_list', [])}
        existing_relations = {
            rel.id_kpp_id: rel
            for rel in ilap.ilap_kpp_relations.all()
        }
        existing_kpp_ids = set(existing_relations.keys())
        
        # Remove relations for KPPs that were deselected
        kpp_ids_to_remove = existing_kpp_ids - selected_kpp_ids
        if kpp_ids_to_remove:
            ILAPKPP.objects.filter(
                id_ilap=ilap,
                id_kpp_id__in=kpp_ids_to_remove
            ).delete()
        
        # Create relations for newly selected KPPs
        kpp_ids_to_add = selected_kpp_ids - existing_kpp_ids
        for kpp_pk in kpp_ids_to_add:
            ILAPKPP.objects.create(id_ilap=ilap, id_kpp_id=kpp_pk)
