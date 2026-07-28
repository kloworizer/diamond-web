from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from .base import AutoRequiredFormMixin
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from ..models.tanda_terima_data import TandaTerimaData
from ..utils import validate_not_future_datetime, combine_date_with_current_time, normalize_server_datetime
from ..utils.tanda_terima_nomor import (
    allocate_nomor_tanda_terima,
    format_nomor_tanda_terima,
    next_nomor_tanda_terima,
    parse_nomor_tanda_terima,
)
from ..utils.tanda_terima_scope import (
    LINGKUP_CHOICES,
    LINGKUP_NASIONAL,
    LINGKUP_REGIONAL,
    is_regional_ilap,
    kanwil_ids_with_available_tiket,
    nasional_ilap_queryset,
    scoped_tiket_queryset,
)
from ..models.tiket import Tiket
from ..models.kanwil import Kanwil
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


# Retries for the nomor_tanda_terima INSERT when a concurrent request takes
# the number first. Each retry re-reads the current maximum.
_NOMOR_ALLOCATION_ATTEMPTS = 5


def scoped_ilap_tiket_pool(user=None):
    """Tikets that are still free for a brand-new ILAP-scoped tanda terima."""
    return Tiket.objects.filter(status_tiket__lt=6, tanda_terima=False).exclude(
        id__in=DetilTandaTerima.objects.filter(
            id_tanda_terima__active=True,
            id_tanda_terima__id_ilap__isnull=False,
        ).values_list('id_tiket_id', flat=True)
    )


class TandaTerimaDataForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form for recording a Tanda Terima.

    Two scopes are supported, driven by the `lingkup` selector:

    - ``regional``: the receipt covers a whole Kanwil. Tikets are gathered
      from every regional ILAP mapped to that Kanwil, whether the mapping
      goes through a KPP (kategori PD) or straight to the Kanwil (kategori
      PV, which has no KPP counterpart).
    - ``nasional``: the receipt covers a single nasional/internasional ILAP.

    In both cases an optional ND Pengantar narrows the tiket list to a single
    delivery letter.
    """

    # Optional: when omitted the scope is inferred from whichever of
    # id_kanwil / id_ilap was submitted, so callers that only know about the
    # ILAP flow keep working unchanged.
    lingkup = forms.ChoiceField(
        choices=LINGKUP_CHOICES,
        initial=LINGKUP_REGIONAL,
        label="Lingkup Tanda Terima",
        required=False,
    )

    tiket_ids = forms.ModelMultipleChoiceField(
        queryset=Tiket.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Pilih Tiket"
    )

    # Override nomor_tanda_terima as CharField to accept formatted string
    nomor_tanda_terima = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'readonly': True}),
        label="Nomor Tanda Terima"
    )

    class Meta:
        model = TandaTerimaData
        fields = ['tanggal_tanda_terima', 'tahun_terima', 'id_kanwil', 'id_ilap', 'nomor_nd_pengantar']
        widgets = {
            'tanggal_tanda_terima': forms.DateInput(attrs={'type': 'date'}),
            'tahun_terima': forms.NumberInput(attrs={'readonly': True}),
            # Options are filled in by the form JS once a scope is chosen; the
            # underlying model field is a CharField, so no choice validation.
            'nomor_nd_pengantar': forms.Select(),
        }

    def clean_tanggal_tanda_terima(self):
        value = self.cleaned_data.get('tanggal_tanda_terima')
        # Disabled on edit: value is the instance's existing datetime (real
        # capture time already recorded), so leave it untouched. Only a
        # freshly-submitted date (create flow) gets stamped with "now".
        if not self.fields['tanggal_tanda_terima'].disabled:
            value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Tanda Terima")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        tiket_pk = kwargs.pop('tiket_pk', None)
        self.tiket_pk = tiket_pk
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'tiket_ids':
                if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                    field.widget.attrs.update({'class': 'form-select'})
                else:
                    field.widget.attrs.update({'class': 'form-control'})

        # Scope fields are conditionally required; `clean` enforces the pair
        # that matches the selected lingkup.
        self.fields['id_kanwil'].required = False
        self.fields['id_ilap'].required = False
        self.fields['nomor_nd_pengantar'].required = False
        self.fields['id_kanwil'].empty_label = "Pilih Kanwil"
        self.fields['id_ilap'].empty_label = "Pilih ILAP"

        self._existing_tiket_ids = set()
        self._disabled_tiket_ids = set(Tiket.objects.filter(status_tiket__gte=8).values_list('id', flat=True))

        # Auto-generate nomor_tanda_terima and tahun_terima for new records
        if not self.instance.pk:
            self.fields['nomor_tanda_terima'].required = False
            self.fields['tahun_terima'].required = False
            tanggal_input = self.data.get('tanggal_tanda_terima') if self.is_bound else None
            tanggal = None
            if tanggal_input:
                tanggal = parse_datetime(tanggal_input)
                if tanggal is None:
                    parsed_d = parse_date(tanggal_input)
                    if parsed_d:
                        import datetime
                        # Combine date with midnight and make timezone aware
                        tanggal = timezone.make_aware(datetime.datetime.combine(parsed_d, datetime.time.min))
            if tanggal is None:
                tanggal = timezone.now()

            tahun = tanggal.year
            self.fields['tahun_terima'].initial = tahun
            # Preview only — `save` re-allocates, since this can go stale
            # between rendering the form and submitting it.
            self.fields['nomor_tanda_terima'].initial = format_nomor_tanda_terima(
                next_nomor_tanda_terima(tahun), tahun
            )
        else:
            self.fields['nomor_tanda_terima'].disabled = True
            self.fields['tahun_terima'].disabled = True
            self.fields['tanggal_tanda_terima'].disabled = True

        # If tiket_pk is provided, remove the tiket_ids field and pre-fill scope
        if tiket_pk:
            # Remove the tiket_ids field entirely
            del self.fields['tiket_ids']
            self._init_single_tiket_scope(Tiket.objects.get(pk=tiket_pk))
        # Pre-select tikets if editing
        elif self.instance.pk:
            self._init_edit_scope()
        else:
            self._init_create_scope()

        if 'tiket_ids' in self.fields:
            self.fields['tiket_ids'].widget = TiketCheckboxSelectMultiple(disabled_ids=self._disabled_tiket_ids)

    # ------------------------------------------------------------------
    # Scope initialisation
    # ------------------------------------------------------------------
    def _lock_scope_fields(self):
        """Freeze the scope selectors — used by the edit and single-tiket flows.

        The ND Pengantar dropdown is normally filled in by the form JS; once
        frozen there is no JS pass, so its single option is rendered here.
        """
        for name in ('lingkup', 'id_kanwil', 'id_ilap', 'nomor_nd_pengantar'):
            self.fields[name].disabled = True

        nomor = self.fields['nomor_nd_pengantar'].initial or ''
        self.fields['nomor_nd_pengantar'].widget.choices = [
            (nomor, nomor or 'Semua ND Pengantar')
        ]

    def _init_single_tiket_scope(self, tiket):
        """Derive the scope from the tiket the form was opened from."""
        ilap = None
        if tiket.id_periode_data and tiket.id_periode_data.id_sub_jenis_data_ilap:
            ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap

        if is_regional_ilap(ilap):
            kanwil = ilap.kanwil
            self.fields['lingkup'].initial = LINGKUP_REGIONAL
            self.fields['id_kanwil'].initial = kanwil
            self.fields['id_kanwil'].queryset = Kanwil.objects.filter(pk=kanwil.pk) if kanwil else Kanwil.objects.none()
        else:
            self.fields['lingkup'].initial = LINGKUP_NASIONAL
            self.fields['id_ilap'].initial = ilap
            self.fields['id_ilap'].queryset = ILAP.objects.filter(pk=ilap.pk) if ilap else ILAP.objects.none()

        self.fields['nomor_nd_pengantar'].initial = tiket.nomor_surat_pengantar or ''
        self._lock_scope_fields()

    def _init_edit_scope(self):
        """Keep the recorded scope read-only and list its tikets."""
        self._existing_tiket_ids = set(
            DetilTandaTerima.objects.filter(id_tanda_terima_id=self.instance.pk)
            .values_list('id_tiket_id', flat=True)
        )

        instance = self.instance
        self.fields['lingkup'].initial = LINGKUP_REGIONAL if instance.id_kanwil_id else LINGKUP_NASIONAL
        self.fields['id_kanwil'].initial = instance.id_kanwil
        self.fields['id_ilap'].initial = instance.id_ilap
        self.fields['nomor_nd_pengantar'].initial = instance.nomor_nd_pengantar or ''
        if instance.id_kanwil_id:
            self.fields['id_kanwil'].queryset = Kanwil.objects.filter(pk=instance.id_kanwil_id)
        if instance.id_ilap_id:
            self.fields['id_ilap'].queryset = ILAP.objects.filter(pk=instance.id_ilap_id)
        self._lock_scope_fields()

        available_ids = set(
            scoped_tiket_queryset(
                kanwil_id=instance.id_kanwil_id,
                ilap_id=instance.id_ilap_id,
                nomor_nd_pengantar=instance.nomor_nd_pengantar or None,
                exclude_tanda_terima_id=instance.pk,
                max_status=8,
            ).values_list('id', flat=True)
        )

        # SET QUERYSET FIRST before initial! The already-linked tikets stay
        # selectable even when the scope no longer offers them.
        self.fields['tiket_ids'].queryset = Tiket.objects.filter(
            id__in=available_ids | self._existing_tiket_ids
        )
        # NOW set initial AFTER queryset is set
        self.fields['tiket_ids'].initial = list(self._existing_tiket_ids)

        self._disabled_tiket_ids |= self._existing_tiket_ids

    def _init_create_scope(self):
        """Offer only the Kanwil / ILAP that actually have selectable tikets."""
        # Options are added by the form JS once a Kanwil/ILAP is picked; this
        # is just the placeholder so the control is never an empty select.
        self.fields['nomor_nd_pengantar'].widget.choices = [('', 'Semua ND Pengantar')]

        kanwil_ids = kanwil_ids_with_available_tiket(user=self.user, max_status=6)
        self.fields['id_kanwil'].queryset = Kanwil.objects.filter(id__in=kanwil_ids)

        ilap_qs = nasional_ilap_queryset().filter(
            jenisdatailap__periodejenisdata__tiket__in=scoped_ilap_tiket_pool(self.user)
        ).distinct()
        # Restrict ILAP to active P3DE PIC for non-admin users
        if self.user and not (self.user.is_superuser or self.user.groups.filter(name='admin').exists()):
            from ..views.mixins import get_active_p3de_ilap_ids
            pic_ilap_ids = set(get_active_p3de_ilap_ids(self.user))
            ilap_qs = ilap_qs.filter(id__in=pic_ilap_ids)
        self.fields['id_ilap'].queryset = ilap_qs

        # Bind the tiket list to the submitted scope so validation sees the
        # same options the browser rendered.
        if self.is_bound:
            self.fields['tiket_ids'].queryset = scoped_tiket_queryset(
                kanwil_id=self.data.get('id_kanwil') or None,
                ilap_id=self.data.get('id_ilap') or None,
                nomor_nd_pengantar=self.data.get('nomor_nd_pengantar') or None,
                user=self.user,
                max_status=8,
            )
        else:
            self.fields['tiket_ids'].queryset = Tiket.objects.none()

    # ------------------------------------------------------------------
    # Cleaning
    # ------------------------------------------------------------------
    def _disabled_initial(self, name):
        """Value of a disabled field: Django keeps the initial, not the POST."""
        return self.fields[name].initial

    def clean_lingkup(self):
        if self.fields['lingkup'].disabled:
            return self._disabled_initial('lingkup')
        return self.cleaned_data.get('lingkup')

    def clean_id_ilap(self):
        if self.fields['id_ilap'].disabled:
            return self._disabled_initial('id_ilap')
        return self.cleaned_data.get('id_ilap')

    def clean_id_kanwil(self):
        if self.fields['id_kanwil'].disabled:
            return self._disabled_initial('id_kanwil')
        return self.cleaned_data.get('id_kanwil')

    def clean_nomor_nd_pengantar(self):
        if self.fields['nomor_nd_pengantar'].disabled:
            return self._disabled_initial('nomor_nd_pengantar') or ''
        return self.cleaned_data.get('nomor_nd_pengantar') or ''

    def clean(self):
        cleaned_data = super().clean()

        kanwil = cleaned_data.get('id_kanwil')
        ilap = cleaned_data.get('id_ilap')

        # Infer the scope when the selector was not submitted.
        lingkup = cleaned_data.get('lingkup')
        if not lingkup:
            if kanwil:
                lingkup = LINGKUP_REGIONAL
            elif ilap:
                lingkup = LINGKUP_NASIONAL
            cleaned_data['lingkup'] = lingkup

        if lingkup == LINGKUP_REGIONAL:
            if not kanwil:
                self.add_error('id_kanwil', 'Kanwil harus dipilih untuk tanda terima regional.')
            cleaned_data['id_ilap'] = None
        elif lingkup == LINGKUP_NASIONAL:
            if not ilap:
                self.add_error('id_ilap', 'ILAP harus dipilih untuk tanda terima nasional/internasional.')
            cleaned_data['id_kanwil'] = None
        else:
            self.add_error('id_kanwil', 'Kanwil atau ILAP harus dipilih.')

        tanggal = cleaned_data.get('tanggal_tanda_terima')
        if tanggal:
            if self.tiket_pk:
                tikets = Tiket.objects.filter(pk=self.tiket_pk)
            else:
                tikets = cleaned_data.get('tiket_ids') or Tiket.objects.none()
            tanggal = normalize_server_datetime(tanggal)
            for tiket in tikets:
                if tiket.tgl_terima_dip:
                    tgl_terima_dip = normalize_server_datetime(tiket.tgl_terima_dip)
                    if tanggal < tgl_terima_dip:
                        raise ValidationError(
                            f'Tanggal Tanda Terima tidak boleh sebelum Tanggal Terima DIP '
                            f'({tgl_terima_dip.strftime("%d/%m/%Y %H:%M")}) '
                            f'untuk tiket {tiket.nomor_tiket}.'
                        )
        return cleaned_data

    def clean_tiket_ids(self):
        if 'tiket_ids' not in self.fields:
            return self.cleaned_data.get('tiket_ids')

        # Get newly selected tikets (from form submission)
        tiket_objs = self.cleaned_data.get('tiket_ids', [])
        if tiket_objs:
            tiket_ids = set(tiket_objs.values_list('id', flat=True))
        else:
            tiket_ids = set()

        # When editing, include the existing (disabled) tikets in the list
        if self.instance.pk and self._existing_tiket_ids:
            tiket_ids |= self._existing_tiket_ids

        if not tiket_ids:
            raise ValidationError('Minimal satu tiket harus dipilih.')

        # Every selected tiket must belong to the submitted scope and not be
        # taken by another active tanda terima of that same scope.
        available_ids = set(
            scoped_tiket_queryset(
                kanwil_id=self.data.get('id_kanwil') or self.instance.id_kanwil_id or None,
                ilap_id=self.data.get('id_ilap') or self.instance.id_ilap_id or None,
                nomor_nd_pengantar=(
                    self.data.get('nomor_nd_pengantar')
                    or self.instance.nomor_nd_pengantar
                    or None
                ),
                exclude_tanda_terima_id=self.instance.pk or None,
                max_status=8,
            ).values_list('id', flat=True)
        )
        if self.instance.pk:
            available_ids |= self._existing_tiket_ids

        if not tiket_ids.issubset(available_ids):
            raise ValidationError('Beberapa tiket tidak tersedia untuk dipilih.')

        return Tiket.objects.filter(id__in=tiket_ids)

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Only one of the two scope columns is kept; `clean` already decided
        # which, but the ModelForm assignment happens after that.
        if self.cleaned_data.get('lingkup') == LINGKUP_REGIONAL:
            instance.id_ilap = None
        elif self.cleaned_data.get('lingkup') == LINGKUP_NASIONAL:
            instance.id_kanwil = None

        # `nomor_tanda_terima` is not in Meta.fields, so it is handled here.
        # The posted value is only a hint: it is rendered read-only but can
        # still be stale by the time it arrives (someone else took it, or the
        # user changed the date and moved into another year's series). The
        # year always follows the date, and the number is re-allocated
        # whenever the hint is already taken.
        if not instance.pk:
            tahun = instance.tanggal_tanda_terima.year if instance.tanggal_tanda_terima else instance.tahun_terima
            instance.tahun_terima = tahun
            preferred = parse_nomor_tanda_terima(
                self.cleaned_data.get('nomor_tanda_terima'), expected_tahun=tahun
            )
        else:
            preferred = None

        if not commit:
            if not instance.pk:
                instance.nomor_tanda_terima = allocate_nomor_tanda_terima(
                    instance.tahun_terima, preferred=preferred
                )
            return instance

        if instance.pk:
            instance.save()
            self.save_m2m()
            return instance

        # Two users can still read the same "next" number before either
        # commits, so the losing INSERT is retried against a fresh allocation
        # rather than surfacing as a 500.
        for attempt in range(_NOMOR_ALLOCATION_ATTEMPTS):
            instance.nomor_tanda_terima = allocate_nomor_tanda_terima(
                instance.tahun_terima,
                preferred=preferred if attempt == 0 else None,
            )
            try:
                with transaction.atomic():
                    instance.save()
                break
            except IntegrityError:
                if attempt == _NOMOR_ALLOCATION_ATTEMPTS - 1:
                    raise
                instance.pk = None

        self.save_m2m()
        return instance
