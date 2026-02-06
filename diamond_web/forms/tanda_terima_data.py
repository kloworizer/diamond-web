from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ..models.tanda_terima_data import TandaTerimaData
from ..models.tiket import Tiket
from ..models.ilap import ILAP
from ..models.detil_tanda_terima import DetilTandaTerima


class TiketCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    def __init__(self, *args, **kwargs):
        self.disabled_ids = set(kwargs.pop('disabled_ids', []))
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        try:
            value_id = int(value)
        except (TypeError, ValueError):
            value_id = None
        if value_id in self.disabled_ids:
            option['attrs']['disabled'] = True
        return option


class TandaTerimaDataForm(forms.ModelForm):
    tiket_ids = forms.ModelMultipleChoiceField(
        queryset=Tiket.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Pilih Tiket"
    )
    
    class Meta:
        model = TandaTerimaData
        fields = ['tanggal_tanda_terima', 'nomor_tanda_terima', 'deskripsi', 'id_ilap']
        widgets = {
            'tanggal_tanda_terima': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'deskripsi': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        tiket_pk = kwargs.pop('tiket_pk', None)
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'tiket_ids':
                field.widget.attrs.update({'class': 'form-control'})

        self._existing_tiket_ids = set()
        self._disabled_tiket_ids = set(Tiket.objects.filter(status__gte=6).values_list('id', flat=True))

        # Auto-generate nomor_tanda_terima for new records
        if not self.instance.pk:
            self.fields['nomor_tanda_terima'].required = False
            self.fields['nomor_tanda_terima'].widget.attrs.update({'readonly': True})
            tanggal_input = self.data.get('tanggal_tanda_terima') if self.is_bound else None
            tanggal = parse_datetime(tanggal_input) if tanggal_input else None
            self.fields['nomor_tanda_terima'].initial = self._generate_nomor_tanda_terima(tanggal=tanggal)
        else:
            self.fields['nomor_tanda_terima'].disabled = True
        
        # If tiket_pk is provided, remove the tiket_ids field and pre-fill id_ilap
        if tiket_pk:
            # Remove the tiket_ids field entirely
            del self.fields['tiket_ids']
            # Pre-fill id_ilap from tiket
            tiket = Tiket.objects.get(pk=tiket_pk)
            if tiket.id_periode_data:
                self.fields['id_ilap'].initial = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
            # Disable ILAP dropdown for single tiket flow
            self.fields['id_ilap'].disabled = True
        # Pre-select tikets if editing
        elif self.instance.pk:
            self._existing_tiket_ids = set(self.instance.detil_items.values_list('id_tiket_id', flat=True))
            self.fields['tiket_ids'].initial = list(self._existing_tiket_ids)
            self.fields['id_ilap'].disabled = True
        else:
            # Create flow: limit ILAP to those with available tikets
            available_tiket_ids = Tiket.objects.filter(
                status__lt=6
            ).exclude(
                id__in=DetilTandaTerima.objects.values_list('id_tiket_id', flat=True)
            ).values_list('id', flat=True)
            ilap_ids = ILAP.objects.filter(
                jenisdatailap__periodejenisdata__tiket__id__in=available_tiket_ids
            ).values_list('id', flat=True).distinct()
            self.fields['id_ilap'].queryset = ILAP.objects.filter(id__in=ilap_ids)

            # Bind tiket list to selected ILAP when form is bound
            selected_ilap = self.data.get('id_ilap') if self.is_bound else None
            if selected_ilap:
                self.fields['tiket_ids'].queryset = Tiket.objects.filter(
                    status__lt=6,
                    id_periode_data__id_sub_jenis_data_ilap__id_ilap_id=selected_ilap
                ).exclude(
                    id__in=DetilTandaTerima.objects.values_list('id_tiket_id', flat=True)
                )
            else:
                # Empty tiket list until ILAP selected
                self.fields['tiket_ids'].queryset = Tiket.objects.none()

        if 'tiket_ids' in self.fields:
            self.fields['tiket_ids'].widget = TiketCheckboxSelectMultiple(disabled_ids=self._disabled_tiket_ids)

    def clean_id_ilap(self):
        if self.fields['id_ilap'].disabled:
            return self.fields['id_ilap'].initial
        return self.cleaned_data.get('id_ilap')

    def clean_tiket_ids(self):
        if 'tiket_ids' not in self.fields:
            return self.cleaned_data.get('tiket_ids')

        tiket_ids = set(self.cleaned_data.get('tiket_ids').values_list('id', flat=True))
        if self.instance.pk:
            tiket_ids |= self._disabled_tiket_ids & self._existing_tiket_ids

        if not tiket_ids:
            raise ValidationError('Minimal satu tiket harus dipilih.')

        available_ids = set(
            Tiket.objects.filter(status__lt=6)
            .exclude(id__in=DetilTandaTerima.objects.values_list('id_tiket_id', flat=True))
            .values_list('id', flat=True)
        )
        if self.instance.pk:
            available_ids |= self._existing_tiket_ids

        if not tiket_ids.issubset(available_ids | (self._disabled_tiket_ids & self._existing_tiket_ids)):
            raise ValidationError('Beberapa tiket tidak tersedia untuk dipilih.')

        return Tiket.objects.filter(id__in=tiket_ids)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.pk or not instance.nomor_tanda_terima:
            instance.nomor_tanda_terima = self._generate_nomor_tanda_terima(
                tanggal=self.cleaned_data.get('tanggal_tanda_terima')
            )
        if commit:
            instance.save()
            self.save_m2m()
        return instance

    def _generate_nomor_tanda_terima(self, tanggal=None):
        """Generate nomor_tanda_terima with 5-digit sequence/year format."""
        tahun = (tanggal or timezone.now()).year
        suffix = f"/{tahun}"

        existing_numbers = TandaTerimaData.objects.filter(
            nomor_tanda_terima__endswith=suffix
        ).values_list('nomor_tanda_terima', flat=True)

        max_seq = 0
        for nomor in existing_numbers:
            try:
                seq_part = nomor.split('/')[0]
                max_seq = max(max_seq, int(seq_part))
            except Exception:
                continue

        next_seq = max_seq + 1
        return f"{str(next_seq).zfill(5)}/{tahun}"
