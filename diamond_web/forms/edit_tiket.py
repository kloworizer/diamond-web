from django import forms
from django.db.models import Q
from datetime import datetime
from ..models.tiket import Tiket
from ..models.bentuk_data import BentukData
from ..models.status_penelitian import StatusPenelitian
from .base import AutoRequiredFormMixin
from ..constants.tiket_status import (
    STATUS_LABELS,
    STATUS_DIREKAM,
    STATUS_DITELITI,
    STATUS_DIKEMBALIKAN,
)
from ..utils import validate_not_future_datetime, normalize_server_datetime, combine_date_with_current_time


class EditTiketForm(AutoRequiredFormMixin, forms.ModelForm):
    """Edit the isian of an existing tiket.

    A tiket may only be edited by its active P3DE PIC while it is in status
    Direkam and no tanda terima has been created yet; P3DE admins may edit at
    any status (both enforced in the view).

    The editable fields mirror the recording (rekam) form and reuse the exact
    same validation rules. ILAP / jenis data ILAP / status ketersediaan are
    intentionally NOT editable here — they establish the tiket's identity and
    changing them would invalidate the generated nomor tiket and PIC
    assignments.

    P3DE administrators additionally get the later workflow isian (hasil
    penelitian and pengiriman ke PIDE) so a tiket can be corrected after it has
    moved past Direkam. Those fields are dropped entirely for a PIC edit, and
    they never change `status_tiket` — an edit only rewrites the isian, the
    workflow position is moved by the dedicated actions.

    Because the status is not moved by an edit, isian that the current status
    depends on may be corrected but not emptied: a tiket sitting in "Dikirim ke
    PIDE" without an ND Nadine would contradict its own status. Those fields
    are locked against nulling (see `_lock_recorded_workflow_isian`).
    """

    #: Extra isian only a P3DE admin may edit, grouped as they are validated.
    PENELITIAN_FIELDS = ('tgl_teliti', 'baris_lengkap', 'baris_tidak_lengkap')
    PENGIRIMAN_PIDE_FIELDS = ('tgl_nadine', 'nomor_nd_nadine', 'tgl_kirim_pide')
    ADMIN_FIELDS = PENELITIAN_FIELDS + PENGIRIMAN_PIDE_FIELDS

    #: Statuses at which a step has not happened yet. Its isian is then not
    #: part of the tiket and is left out of the form entirely, so an edit can
    #: never write isian that contradicts the status (docs/status_tiket_flow.md:
    #: penelitian happens on the way out of Direkam, pengiriman ke PIDE on the
    #: way out of Diteliti).
    STATUSES_BEFORE_PENELITIAN = (STATUS_DIREKAM,)
    STATUSES_BEFORE_PENGIRIMAN_PIDE = (
        STATUS_DIREKAM, STATUS_DITELITI, STATUS_DIKEMBALIKAN,
    )

    class Meta:
        model = Tiket
        fields = [
            'periode', 'tahun', 'penyampaian',
            'nomor_surat_pengantar', 'tanggal_surat_pengantar', 'nama_pengirim',
            'id_bentuk_data', 'id_cara_penyampaian', 'baris_diterima',
            'tgl_terima_vertikal', 'tgl_terima_dip',
            'tgl_teliti', 'baris_lengkap', 'baris_tidak_lengkap',
            'tgl_nadine', 'nomor_nd_nadine', 'tgl_kirim_pide',
        ]
        widgets = {
            'periode': forms.Select(attrs={'class': 'form-control', 'id': 'id_edit_periode'}),
            'tahun': forms.Select(attrs={'class': 'form-control', 'id': 'id_edit_tahun'}),
            'penyampaian': forms.NumberInput(attrs={
                'class': 'form-control', 'id': 'id_edit_penyampaian',
                'readonly': True, 'style': 'background-color: #e9ecef;', 'min': '0',
            }),
            'nomor_surat_pengantar': forms.TextInput(attrs={'class': 'form-control'}),
            'tanggal_surat_pengantar': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'},
                format='%Y-%m-%d',
            ),
            'nama_pengirim': forms.TextInput(attrs={'class': 'form-control'}),
            'id_bentuk_data': forms.Select(attrs={'class': 'form-control'}),
            'id_cara_penyampaian': forms.Select(attrs={'class': 'form-control'}),
            'baris_diterima': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_edit_baris_diterima', 'min': '0'}),
            'tgl_terima_vertikal': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control', 'id': 'id_edit_tgl_terima_vertikal'},
                format='%Y-%m-%d',
            ),
            'tgl_terima_dip': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control', 'id': 'id_edit_tgl_terima_dip'},
                format='%Y-%m-%d',
            ),
            'tgl_teliti': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control', 'id': 'id_edit_tgl_teliti'},
                format='%Y-%m-%d',
            ),
            'baris_lengkap': forms.NumberInput(attrs={
                'class': 'form-control', 'id': 'id_edit_baris_lengkap', 'min': '0',
            }),
            'baris_tidak_lengkap': forms.NumberInput(attrs={
                'class': 'form-control', 'id': 'id_edit_baris_tidak_lengkap', 'min': '0',
            }),
            'tgl_nadine': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control', 'id': 'id_edit_tgl_nadine'},
                format='%Y-%m-%d',
            ),
            'nomor_nd_nadine': forms.TextInput(attrs={'class': 'form-control'}),
            'tgl_kirim_pide': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control', 'id': 'id_edit_tgl_kirim_pide'},
                format='%Y-%m-%d',
            ),
        }

    def __init__(self, *args, is_admin=False, **kwargs):
        self.is_admin = is_admin
        super().__init__(*args, **kwargs)

        # The later workflow isian is an admin-only correction tool, and only
        # for steps the tiket has actually been through: a Direkam tiket has no
        # hasil penelitian to correct. Fields outside that are removed from the
        # form entirely, so they can neither be rendered, posted, nor emptied
        # by a submit that leaves them out.
        self.show_penelitian = is_admin and self._step_reached(self.STATUSES_BEFORE_PENELITIAN)
        self.show_pengiriman_pide = is_admin and self._step_reached(
            self.STATUSES_BEFORE_PENGIRIMAN_PIDE
        )
        if not self.show_penelitian:
            for name in self.PENELITIAN_FIELDS:
                self.fields.pop(name, None)
        if not self.show_pengiriman_pide:
            for name in self.PENGIRIMAN_PIDE_FIELDS:
                self.fields.pop(name, None)

        for name in ('tgl_teliti', 'tgl_nadine', 'tgl_kirim_pide'):
            if name in self.fields:
                self.fields[name].input_formats = [
                    '%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
                ]
        self._lock_recorded_workflow_isian()

        # Year choices (current year to 20 years back), same as the rekam form.
        current_year = datetime.now().year
        year_choices = [(year, str(year)) for year in range(current_year - 20, current_year + 1)]
        self.fields['tahun'].widget.choices = year_choices

        # Periode options depend on the periode penerimaan and are populated
        # client-side. Seed the widget with the stored value so it renders as
        # the selected option before the JS repopulates the dropdown.
        if self.instance and self.instance.pk and self.instance.periode is not None:
            self.fields['periode'].widget.choices = [(self.instance.periode, str(self.instance.periode))]

        # Hide the "Data Tidak Tersedia" bentuk data option: a tiket recorded
        # with available data must not be switched to it here (mirrors the
        # rekam form which hides it client-side). The tiket's own bentuk data
        # is always kept selectable — a P3DE admin may edit a "data tidak
        # tersedia" tiket, and dropping its current value would force an
        # unrelated change before the form could be saved.
        bentuk_data_qs = BentukData.objects.exclude(deskripsi__icontains='tidak tersedia')
        current_bentuk_data_id = getattr(self.instance, 'id_bentuk_data_id', None)
        if current_bentuk_data_id:
            bentuk_data_qs = BentukData.objects.filter(
                Q(pk=current_bentuk_data_id) | ~Q(deskripsi__icontains='tidak tersedia')
            )
        self.fields['id_bentuk_data'].queryset = bentuk_data_qs

        # Surat pengantar fields and tanggal terima vertikal are optional
        # (mirrors the rekam form).
        self.fields['nomor_surat_pengantar'].required = False
        self.fields['tanggal_surat_pengantar'].required = False
        self.fields['nama_pengirim'].required = False
        self.fields['tgl_terima_vertikal'].required = False

    def clean_tgl_terima_vertikal(self):
        value = self.cleaned_data.get('tgl_terima_vertikal')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Terima Vertikal")

    def clean_tgl_terima_dip(self):
        value = self.cleaned_data.get('tgl_terima_dip')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Terima DIP")

    def clean_tanggal_surat_pengantar(self):
        value = self.cleaned_data.get('tanggal_surat_pengantar')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Surat Pengantar")

    def clean_tgl_teliti(self):
        value = self.cleaned_data.get('tgl_teliti')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Teliti")

    def clean_tgl_nadine(self):
        value = self.cleaned_data.get('tgl_nadine')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Nadine")

    def clean_tgl_kirim_pide(self):
        value = self.cleaned_data.get('tgl_kirim_pide')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Kirim PIDE")

    def _step_reached(self, before_statuses):
        """True when the tiket is past the workflow step described by a group."""
        return getattr(self.instance, 'status_tiket', None) not in before_statuses

    def _lock_recorded_workflow_isian(self):
        """Protect the isian the current status depends on against nulling.

        An edit never moves `status_tiket`, so clearing e.g. the ND Nadine of a
        tiket that is already "Dikirim ke PIDE" would leave the tiket
        contradicting its own status. Such fields stay editable — they just
        cannot be emptied, and say why.

        Only isian the tiket actually carries is protected: the guard is
        against *nulling* recorded data, never a demand to fill in a step that
        was never recorded. Plenty of tikets sit past a step without every one
        of its fields — many were migrated from the old database, where e.g. a
        tiket can be "Dikirim ke PIDE" with no tanggal teliti at all.
        """
        status_label = STATUS_LABELS.get(
            getattr(self.instance, 'status_tiket', None), 'saat ini'
        )
        for name in self.ADMIN_FIELDS:
            if name not in self.fields:
                continue
            if getattr(self.instance, name, None) in (None, ''):
                continue
            field = self.fields[name]
            field.required = True
            field.error_messages['required'] = (
                f'{field.label} tidak boleh dikosongkan karena status tiket '
                f'"{status_label}".'
            )

    def _is_changed(self, *field_names):
        """True when this edit actually changes one of *field_names*.

        Compared against the stored tiket (`self.instance` is still untouched
        during `clean()`) and by date for the datetime columns: their widgets
        are date-only, so Django's own `changed_data` flags every one of them
        as changed on every submit.

        Chronology rules are checked only for what the edit touches. Tikets
        migrated from the old database do carry combinations these rules
        reject — an admin correcting an unrelated field on such a tiket must
        not be blocked by data they did not write.
        """
        for name in field_names:
            if name not in self.fields:
                continue
            new = self.cleaned_data.get(name)
            old = getattr(self.instance, name, None)
            if isinstance(new, datetime):
                new = normalize_server_datetime(new).date()
            if isinstance(old, datetime):
                old = normalize_server_datetime(old).date()
            if new != old:
                return True
        return False

    def _clean_baris_diterima(self, cleaned_data):
        """Keep baris diterima equal to baris lengkap + baris tidak lengkap.

        The rule holds for every edit, not just the ones that show the baris
        lengkap fields: baris diterima can still be changed on its own, which
        would break the identity for a tiket that already has hasil penelitian.
        The stored values are then the reference.

        A tiket still in Direkam has no hasil penelitian yet — the zeroes the
        old database left there are not a result — so its baris diterima may be
        corrected freely.
        """
        if self.show_penelitian:
            baris_lengkap = cleaned_data.get('baris_lengkap')
            baris_tidak_lengkap = cleaned_data.get('baris_tidak_lengkap')
        else:
            baris_lengkap = self.instance.baris_lengkap
            baris_tidak_lengkap = self.instance.baris_tidak_lengkap
        # baris_diterima is editable here, so validate against the submitted
        # value rather than the stored one.
        baris_diterima = cleaned_data.get('baris_diterima', self.instance.baris_diterima)

        if baris_lengkap is None or baris_tidak_lengkap is None or baris_diterima is None:
            return
        if self.instance.status_tiket == STATUS_DIREKAM:
            return
        total = baris_lengkap + baris_tidak_lengkap
        if total != baris_diterima:
            self.add_error('baris_diterima', forms.ValidationError(
                f'Baris diterima ({baris_diterima}) harus sama dengan baris lengkap + '
                f'baris tidak lengkap ({baris_lengkap} + {baris_tidak_lengkap} = {total}).'
            ))

    def _clean_hasil_penelitian(self, cleaned_data):
        """Validate the hasil penelitian isian, mirroring the rekam form.

        Baris lengkap and baris tidak lengkap are two halves of baris diterima,
        so they are filled or cleared as a pair. Tanggal teliti stands on its
        own: a tiket may legitimately carry baris values without one.
        """
        baris_lengkap = cleaned_data.get('baris_lengkap')
        baris_tidak_lengkap = cleaned_data.get('baris_tidak_lengkap')
        pair = (
            ('baris_lengkap', baris_lengkap, 'baris_tidak_lengkap', baris_tidak_lengkap),
            ('baris_tidak_lengkap', baris_tidak_lengkap, 'baris_lengkap', baris_lengkap),
        )
        for name, value, other_name, other_value in pair:
            if value is None and other_value is not None and name not in self.errors:
                self.add_error(name, forms.ValidationError(
                    f'{self.fields[name].label} wajib diisi bila '
                    f'{self.fields[other_name].label} diisi.'
                ))

        tgl_teliti = cleaned_data.get('tgl_teliti')
        tgl_dip = cleaned_data.get('tgl_terima_dip')
        if tgl_teliti and tgl_dip and self._is_changed('tgl_teliti', 'tgl_terima_dip'):
            tgl_teliti = normalize_server_datetime(tgl_teliti)
            tgl_dip = normalize_server_datetime(tgl_dip)
            if tgl_teliti < tgl_dip:
                self.add_error('tgl_teliti', forms.ValidationError(
                    'Tanggal Teliti tidak boleh sebelum Tanggal Terima DIP '
                    f'({tgl_dip.strftime("%d/%m/%Y %H:%M")}).'
                ))

    def _clean_pengiriman_pide(self, cleaned_data):
        """Validate the ND Nadine / kirim ke PIDE isian, mirroring that form.

        The three fields are not required as a group: the workflow fills them
        together, but migrated tikets carry them partially and an admin must
        still be able to correct such a tiket.
        """
        tgl_teliti = cleaned_data.get('tgl_teliti')
        tgl_nadine = cleaned_data.get('tgl_nadine')
        tgl_kirim_pide = cleaned_data.get('tgl_kirim_pide')

        if tgl_teliti:
            teliti = normalize_server_datetime(tgl_teliti)
            for name, value, label in (
                ('tgl_nadine', tgl_nadine, 'Tanggal Nadine'),
                ('tgl_kirim_pide', tgl_kirim_pide, 'Tanggal Kirim PIDE'),
            ):
                if not value or not self._is_changed(name, 'tgl_teliti'):
                    continue
                if normalize_server_datetime(value) < teliti:
                    self.add_error(name, forms.ValidationError(
                        f'{label} tidak boleh sebelum Tanggal Teliti '
                        f'({teliti.strftime("%d/%m/%Y %H:%M")}).'
                    ))

        if tgl_nadine and tgl_kirim_pide and self._is_changed('tgl_nadine', 'tgl_kirim_pide'):
            nadine = normalize_server_datetime(tgl_nadine)
            kirim = normalize_server_datetime(tgl_kirim_pide)
            if kirim < nadine:
                self.add_error('tgl_kirim_pide', forms.ValidationError(
                    'Tanggal Kirim PIDE tidak boleh sebelum Tanggal Nadine '
                    f'({nadine.strftime("%d/%m/%Y %H:%M")}).'
                ))

    def clean(self):
        cleaned_data = super().clean()

        # Run these first: the checks below raise, which would otherwise hide
        # every problem in the later workflow isian.
        self._clean_baris_diterima(cleaned_data)
        if self.show_penelitian:
            self._clean_hasil_penelitian(cleaned_data)
        if self.show_pengiriman_pide:
            self._clean_pengiriman_pide(cleaned_data)

        tgl_vertikal = cleaned_data.get('tgl_terima_vertikal')
        tgl_dip = cleaned_data.get('tgl_terima_dip')
        if tgl_vertikal and tgl_dip:
            tgl_vertikal = normalize_server_datetime(tgl_vertikal)
            tgl_dip = normalize_server_datetime(tgl_dip)
            if tgl_dip < tgl_vertikal:
                raise forms.ValidationError(
                    'Tanggal Terima DIP tidak boleh sebelum Tanggal Terima Vertikal '
                    f'({tgl_vertikal.strftime("%d/%m/%Y %H:%M")}).'
                )
        # Validasi: tgl_terima_dip tidak boleh melebihi end_date periode.
        # id_periode_data is not editable here, so read it from the instance.
        id_periode_data = getattr(self.instance, 'id_periode_data', None)
        if id_periode_data and id_periode_data.end_date and tgl_dip:
            tgl_dip = normalize_server_datetime(tgl_dip)
            if tgl_dip.date() > id_periode_data.end_date:
                raise forms.ValidationError(
                    f'Tanggal Terima DIP ({tgl_dip.strftime("%d/%m/%Y %H:%M")}) tidak boleh '
                    f'melebihi end date periode ({id_periode_data.end_date.isoformat()}).'
                )
        return cleaned_data

    def resolve_status_penelitian(self):
        """Return the StatusPenelitian implied by the submitted baris values.

        Uses the same rule as the Rekam Hasil Penelitian form: all rows
        complete → Lengkap, none complete → Tidak Lengkap, otherwise Lengkap
        Sebagian. Returns ``None`` when the hasil penelitian has been cleared,
        and keeps the tiket's current value when the reference data is missing.
        """
        baris_lengkap = self.cleaned_data.get('baris_lengkap')
        if baris_lengkap is None:
            return None
        baris_diterima = self.cleaned_data.get('baris_diterima', self.instance.baris_diterima)
        if baris_lengkap == baris_diterima:
            deskripsi = 'Lengkap'
        elif baris_lengkap == 0:
            deskripsi = 'Tidak Lengkap'
        else:
            deskripsi = 'Lengkap Sebagian'
        status = StatusPenelitian.objects.filter(deskripsi=deskripsi).first()
        return status or self.instance.id_status_penelitian

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Status penelitian is never picked by hand: it follows from the baris
        # values, exactly like in the Rekam Hasil Penelitian form. It is only
        # recalculated when those values were part of the edit — otherwise the
        # tiket keeps the status penelitian it already had.
        if self.show_penelitian:
            instance.id_status_penelitian = self.resolve_status_penelitian()
        if commit:
            instance.save()
        return instance
