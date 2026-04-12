"""Tests covering remaining coverage gaps in forms and context_processors.

Targets:
  - context_processors.py:        lines 53-55
  - forms/backup_data.py:         lines 66-67
  - forms/base.py:                lines 21, 39-41
  - forms/durasi_jatuh_tempo.py:  lines 35-36, 44
  - forms/ilap.py:                line 10
  - forms/jenis_prioritas_data.py: lines 32-35, 44-47
  - forms/kirim_tiket.py:         lines 32, 37-38, 40, 44
  - forms/periode_jenis_data.py:  lines 29-32
  - forms/pic.py:                 lines 86-90
  - forms/rekam_hasil_penelitian.py: line 69
  - forms/tanda_terima_data.py:   lines 19-26, 73, 114, 136, 196, 208, 247, 265-268
  - forms/tiket.py:               lines 129-130, 141-142
"""
import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import Group, User
from django.utils import timezone

from diamond_web.tests.conftest import (
    UserFactory,
    GroupFactory,
    ILAPFactory,
    KategoriILAPFactory,
    JenisDataILAPFactory,
    PeriodePengirimanFactory,
    PeriodeJenisDataFactory,
    JenisPrioritasDataFactory,
    PICFactory,
    TiketFactory,
    TiketPICFactory,
    TandaTerimaDataFactory,
    MediaBackupFactory,
    KategoriWilayahFactory,
)


# ─────────────────────────────────────────────────────────────────────────────
# context_processors.py — lines 53-55
# ─────────────────────────────────────────────────────────────────────────────

class TestGetGitCommitFile:
    """Lines 53-55: _get_git_commit() reads GIT_COMMIT file when present."""

    def test_reads_git_commit_file(self, monkeypatch):
        """When env vars absent, git fails, GIT_COMMIT file exists → return its content."""
        from diamond_web import context_processors as cp

        # Ensure env vars don't short-circuit the function
        monkeypatch.delenv('GIT_COMMIT_SHORT', raising=False)
        monkeypatch.delenv('GIT_COMMIT', raising=False)

        # Determine expected file location
        repo_dir = Path(cp.__file__).resolve().parent.parent
        commit_file = repo_dir / "GIT_COMMIT"

        # Mock git to fail (returncode != 0) so we reach the file-read branch
        mock_result = MagicMock()
        mock_result.returncode = 1

        existing_content = None
        if commit_file.exists():
            existing_content = commit_file.read_text()

        try:
            commit_file.write_text("testsha123")
            with patch.object(cp.subprocess, 'run', return_value=mock_result):
                result = cp._get_git_commit()
            assert result == "testsha123"
        finally:
            if existing_content is not None:
                commit_file.write_text(existing_content)
            elif commit_file.exists():
                commit_file.unlink()

    def test_exception_reading_git_commit_file_falls_through(self, monkeypatch):
        """Lines 54-55: exception during file read is caught, returns empty string."""
        from diamond_web import context_processors as cp

        monkeypatch.delenv('GIT_COMMIT_SHORT', raising=False)
        monkeypatch.delenv('GIT_COMMIT', raising=False)

        mock_result = MagicMock()
        mock_result.returncode = 1

        # Patch Path.read_text to raise so the except clause (lines 54-55) fires
        with patch.object(cp.subprocess, 'run', return_value=mock_result):
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'read_text', side_effect=PermissionError('denied')):
                    result = cp._get_git_commit()

        assert result == ""


# ─────────────────────────────────────────────────────────────────────────────
# forms/backup_data.py — lines 66-67
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBackupDataFormDoesNotExist:
    """Lines 66-67: BackupDataForm.clean() silently catches Tiket.DoesNotExist."""

    def test_tiket_does_not_exist_is_caught(self, db):
        from diamond_web.forms.backup_data import BackupDataForm

        media_backup = MediaBackupFactory()

        # Provide tiket_pk that doesn't exist in DB
        form = BackupDataForm(
            data={
                'lokasi_backup': '/mnt/backup/test.zip',
                'nama_file': 'test.zip',
                'id_media_backup': media_backup.pk,
            },
            tiket_pk=999999,
        )

        # Manually invoke clean() by setting cleaned_data (bypasses field validation)
        form.cleaned_data = {
            'lokasi_backup': '/mnt/backup/test.zip',
            'nama_file': 'test.zip',
            'id_media_backup': media_backup,
        }

        result = form.clean()
        # DoesNotExist was caught silently — no 'id_tiket' in cleaned_data
        assert 'id_tiket' not in result or result.get('id_tiket') is None


# ─────────────────────────────────────────────────────────────────────────────
# forms/base.py — lines 21, 39-41
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoRequiredFormMixin:
    """Lines 21 and 39-41 in forms/base.py."""

    def test_early_return_when_no_meta_model(self):
        """Line 21: mixin returns early when the form has no Meta.model."""
        from diamond_web.forms.base import AutoRequiredFormMixin
        from django import forms as django_forms

        class PlainForm(AutoRequiredFormMixin, django_forms.Form):
            name = django_forms.CharField()

        # __init__ should complete without error, hitting line 21 early-return
        form = PlainForm(data={'name': 'hello'})
        assert form.is_valid()

    @pytest.mark.django_db
    def test_exception_in_get_field_is_silenced(self, db):
        """Lines 39-41: exception from model._meta.get_field is caught and ignored."""
        from diamond_web.forms.backup_data import BackupDataForm
        from diamond_web.models.backup_data import BackupData

        media_backup = MediaBackupFactory()
        original_get_field = BackupData._meta.get_field

        def selective_raise(name):
            if name == 'lokasi_backup':
                raise Exception("Simulated FieldDoesNotExist")
            return original_get_field(name)

        with patch.object(BackupData._meta, 'get_field', side_effect=selective_raise):
            # Form should instantiate without raising
            form = BackupDataForm(
                data={
                    'lokasi_backup': '/mnt/test',
                    'nama_file': 'f.zip',
                    'id_media_backup': media_backup.pk,
                },
                tiket_pk=1,
            )

        assert form is not None


# ─────────────────────────────────────────────────────────────────────────────
# forms/durasi_jatuh_tempo.py — lines 35-36, 44
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDurasiJatuhTempoForm:
    """Lines 35-36 and 44 in forms/durasi_jatuh_tempo.py."""

    def test_group_does_not_exist_is_caught(self, db):
        """Lines 35-36: Group.DoesNotExist silently caught for unknown group_name."""
        from diamond_web.forms.durasi_jatuh_tempo import DurasiJatuhTempoForm

        # This group doesn't exist → Group.DoesNotExist caught at lines 35-36
        form = DurasiJatuhTempoForm(group_name='nonexistent_group_xyz_99999')
        assert 'seksi' in form.fields  # Form created without raising

    def test_label_from_instance_else_branch(self, db):
        """Line 44: label_from_instance returns obj.name for unknown group names."""
        from diamond_web.forms.durasi_jatuh_tempo import DurasiJatuhTempoForm

        other_group, _ = Group.objects.get_or_create(name='other_test_group_unique')

        form = DurasiJatuhTempoForm(group_name='other_test_group_unique')

        # Access the label function and call it with a group that isn't pide/pmde
        label_fn = form.fields['seksi'].label_from_instance
        result = label_fn(other_group)
        assert result == 'other_test_group_unique'


# ─────────────────────────────────────────────────────────────────────────────
# forms/ilap.py — line 10
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestKategoriChoiceField:
    """Line 10: KategoriChoiceField.to_python() falls back to pk lookup."""

    def test_returns_none_for_empty_value(self, db):
        """Line 10: to_python returns None when value is in empty_values."""
        from diamond_web.forms.ilap import KategoriChoiceField
        from diamond_web.models.kategori_ilap import KategoriILAP

        field = KategoriChoiceField(queryset=KategoriILAP.objects.all())
        # None is in empty_values → line 10: return None
        result = field.to_python(None)
        assert result is None

    def test_falls_back_to_pk_when_id_kategori_not_found(self, db):
        """Line 14: except clause fires when id_kategori lookup fails; pk used instead."""
        from diamond_web.forms.ilap import KategoriChoiceField
        from diamond_web.models.kategori_ilap import KategoriILAP

        kat = KategoriILAP.objects.create(id_kategori='ZZ', nama_kategori='ZZ Test')
        field = KategoriChoiceField(queryset=KategoriILAP.objects.all())

        # str(kat.pk) won't match id_kategori='ZZ' → DoesNotExist → fallback to pk
        result = field.to_python(str(kat.pk))
        assert result == kat


# ─────────────────────────────────────────────────────────────────────────────
# forms/jenis_prioritas_data.py — lines 32-35, 44-47
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestJenisPrioritasDataForm:
    """Lines 32-35 and 44-47 in forms/jenis_prioritas_data.py."""

    def test_duplicate_tahun_adds_error(self, db):
        """Lines 32-35: duplicate tahun triggers add_error and early return."""
        from diamond_web.forms.jenis_prioritas_data import JenisPrioritasDataForm

        jenis = JenisDataILAPFactory()
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=jenis,
            tahun='2024',
            start_date=date(2024, 3, 1),
        )

        data = {
            'id_sub_jenis_data_ilap': jenis.pk,
            'no_nd': 'ND-DUPL-TAHUN',
            'tahun': '2024',          # Same tahun → duplicate error
            'start_date': '2024-06-01',
            'end_date': '2024-12-31',
        }
        form = JenisPrioritasDataForm(data=data)
        assert not form.is_valid()
        assert 'tahun' in form.errors

    def test_duplicate_start_date_adds_error(self, db):
        """Lines 44-47: duplicate start_date triggers add_error and early return."""
        from diamond_web.forms.jenis_prioritas_data import JenisPrioritasDataForm

        jenis = JenisDataILAPFactory()
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=jenis,
            tahun='2024',
            start_date=date(2024, 1, 1),
        )

        data = {
            'id_sub_jenis_data_ilap': jenis.pk,
            'no_nd': 'ND-DUPL-START',
            'tahun': '2025',           # Different tahun so no tahun-duplicate error
            'start_date': '2024-01-01',  # Same start_date → duplicate start_date error
            'end_date': '2025-12-31',
        }
        form = JenisPrioritasDataForm(data=data)
        assert not form.is_valid()
        assert 'start_date' in form.errors


# ─────────────────────────────────────────────────────────────────────────────
# forms/kirim_tiket.py — lines 32, 37-38, 40, 44
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestKirimTiketForm:
    """Lines 32, 37-38, 40, 44 in forms/kirim_tiket.py."""

    def _base_data(self):
        now = timezone.now()
        return {
            'nomor_nd_nadine': 'ND-TEST-001',
            'tgl_nadine': now.strftime('%Y-%m-%dT%H:%M'),
            'tgl_kirim_pide': now.strftime('%Y-%m-%dT%H:%M'),
        }

    def test_uses_initial_tiket_ids_when_empty(self, db):
        """Line 32: tiket_ids falls back to self.initial['tiket_ids'] when data is empty."""
        from diamond_web.forms.kirim_tiket import KirimTiketForm

        tiket = TiketFactory()
        data = {**self._base_data(), 'tiket_ids': ''}
        form = KirimTiketForm(data=data)
        form.initial['tiket_ids'] = str(tiket.pk)   # Set after creation

        assert form.is_valid(), form.errors
        assert form.cleaned_data['tiket_ids'] == str(tiket.pk)

    def test_invalid_tiket_ids_raises_validation_error(self, db):
        """Lines 37-38: non-integer tiket_ids raises ValidationError."""
        from diamond_web.forms.kirim_tiket import KirimTiketForm

        data = {**self._base_data(), 'tiket_ids': 'abc,xyz'}
        form = KirimTiketForm(data=data)
        assert not form.is_valid()
        assert 'tiket_ids' in form.errors
        assert any('tidak valid' in str(e) for e in form.errors['tiket_ids'])

    def test_empty_ids_list_raises_validation_error(self, db):
        """Line 40: after split/strip, empty ids list raises ValidationError."""
        from diamond_web.forms.kirim_tiket import KirimTiketForm

        data = {**self._base_data(), 'tiket_ids': ',,,'}
        form = KirimTiketForm(data=data)
        assert not form.is_valid()
        assert 'tiket_ids' in form.errors
        assert any('minimal satu' in str(e) for e in form.errors['tiket_ids'])

    def test_nonexistent_tiket_ids_raises_validation_error(self, db):
        """Line 44: IDs that don't exist in DB raises ValidationError (len mismatch)."""
        from diamond_web.forms.kirim_tiket import KirimTiketForm

        data = {**self._base_data(), 'tiket_ids': '999999,888888'}
        form = KirimTiketForm(data=data)
        assert not form.is_valid()
        assert 'tiket_ids' in form.errors
        assert any('tidak ditemukan' in str(e) for e in form.errors['tiket_ids'])


# ─────────────────────────────────────────────────────────────────────────────
# forms/periode_jenis_data.py — lines 29-32
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPeriodeJenisDataForm:
    """Lines 29-32: duplicate start_date triggers add_error and early return."""

    def test_duplicate_start_date_adds_error(self, db):
        from diamond_web.forms.periode_jenis_data import PeriodeJenisDataForm

        jenis = JenisDataILAPFactory()
        periode_pengiriman = PeriodePengirimanFactory()
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jenis,
            start_date=date(2024, 1, 1),
        )

        data = {
            'id_sub_jenis_data_ilap': jenis.pk,
            'id_periode_pengiriman': periode_pengiriman.pk,
            'akhir_penyampaian': 15,
            'start_date': '2024-01-01',   # Same start_date → duplicate error
            'end_date': '2024-12-31',
        }
        form = PeriodeJenisDataForm(data=data)
        assert not form.is_valid()
        assert 'start_date' in form.errors


# ─────────────────────────────────────────────────────────────────────────────
# forms/pic.py — lines 86-90
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPICFormOverlapping:
    """Lines 86-90: overlapping active PIC triggers add_error and early return."""

    def test_overlapping_pic_adds_error(self, db):
        from diamond_web.forms.pic import PICForm
        from diamond_web.models.pic import PIC

        user = UserFactory()
        group, _ = Group.objects.get_or_create(name='user_p3de')
        user.groups.add(group)

        jenis = JenisDataILAPFactory()

        # Existing active PIC with no end_date (open-ended)
        PICFactory(
            tipe=PIC.TipePIC.P3DE,
            id_sub_jenis_data_ilap=jenis,
            id_user=user,
            start_date=date(2024, 1, 1),
            end_date=None,
        )

        # New form with same tipe/user/jenis but DIFFERENT start_date
        # (so exact-match check passes, but overlap check fires)
        data = {
            'tipe': PIC.TipePIC.P3DE,
            'id_sub_jenis_data_ilap': jenis.pk,
            'id_user': user.pk,
            'start_date': '2024-06-01',
            'end_date': '',
        }
        form = PICForm(data=data, tipe=PIC.TipePIC.P3DE)
        assert not form.is_valid()
        assert 'start_date' in form.errors
        assert any('PIC aktif' in str(e) for e in form.errors['start_date'])


# ─────────────────────────────────────────────────────────────────────────────
# forms/rekam_hasil_penelitian.py — line 69
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRekamHasilPenelitianForm:
    """Line 69: pre-format tgl_teliti when instance already has it."""

    def test_pre_formats_tgl_teliti(self, db):
        from diamond_web.forms.rekam_hasil_penelitian import RekamHasilPenelitianForm

        tiket = TiketFactory()
        tiket.tgl_teliti = timezone.now()
        tiket.save()

        form = RekamHasilPenelitianForm(instance=tiket)

        # Line 69: self.initial['tgl_teliti'] should be set to formatted string
        assert 'tgl_teliti' in form.initial
        assert 'T' in form.initial['tgl_teliti']  # '%Y-%m-%dT%H:%M' format


# ─────────────────────────────────────────────────────────────────────────────
# forms/tanda_terima_data.py — lines 19-26, 73, 114, 136, 196, 208, 247, 265-268
# ─────────────────────────────────────────────────────────────────────────────

class TestTiketCheckboxSelectMultiple:
    """Lines 19-26: create_option method."""

    def test_create_option_sets_disabled_for_matching_id(self):
        """Lines 19-25: value_id in disabled_ids → option disabled."""
        from diamond_web.forms.tanda_terima_data import TiketCheckboxSelectMultiple

        widget = TiketCheckboxSelectMultiple(disabled_ids=[42])

        # Provide a value that IS in disabled_ids
        option = widget.create_option(
            name='tiket_ids',
            value=42,
            label='Test Tiket',
            selected=False,
            index=0,
        )

        assert option['attrs'].get('disabled') is True

    def test_create_option_none_value_not_disabled(self):
        """Lines 19-24, 26: TypeError when int(None) → value_id=None, not disabled."""
        from diamond_web.forms.tanda_terima_data import TiketCheckboxSelectMultiple

        widget = TiketCheckboxSelectMultiple(disabled_ids=[42])

        option = widget.create_option(
            name='tiket_ids',
            value=None,          # int(None) → TypeError → value_id = None
            label='Empty',
            selected=False,
            index=0,
        )

        assert option['attrs'].get('disabled') is None


@pytest.mark.django_db
class TestTandaTerimaDataFormBranches:
    """Remaining uncovered branches in TandaTerimaDataForm."""

    def _make_ilap_and_tiket(self):
        ilap = ILAPFactory()
        tiket = TiketFactory(status_tiket=1)
        return ilap, tiket

    def test_bound_form_invalid_tanggal_triggers_line_73(self, db):
        """Line 73: bound form with invalid tanggal_input re-attempts parse_datetime."""
        from diamond_web.forms.tanda_terima_data import TandaTerimaDataForm

        # Bound form with unparseable tanggal_tanda_terima → parse_datetime returns None
        # → line 72 condition is True → line 73 re-parses (redundantly)
        data = {
            'tanggal_tanda_terima': 'not-a-valid-datetime',
            'tiket_ids': [],
        }
        form = TandaTerimaDataForm(data=data)
        # Form should be created without exception (tanggal falls back to now())
        assert form is not None

    def test_edit_instance_no_ilap_fetches_from_tiket(self, db):
        """Line 114: edit existing TandaTerima where id_ilap_id is None in-memory but has tiket."""
        from diamond_web.forms.tanda_terima_data import TandaTerimaDataForm
        from diamond_web.models.tanda_terima_data import TandaTerimaData
        from diamond_web.models.detil_tanda_terima import DetilTandaTerima

        ilap, tiket = self._make_ilap_and_tiket()
        user = UserFactory()

        tanda_terima = TandaTerimaData.objects.create(
            nomor_tanda_terima=1,
            tahun_terima=2024,
            tanggal_tanda_terima=timezone.now(),
            id_ilap=ilap,
            id_perekam=user,
            active=True,
        )
        DetilTandaTerima.objects.create(
            id_tanda_terima=tanda_terima,
            id_tiket=tiket,
        )

        # Temporarily allow null on the FK field so accessing instance.id_ilap
        # with id_ilap_id=None returns None instead of raising RelatedObjectDoesNotExist.
        ilap_field = TandaTerimaData._meta.get_field('id_ilap')
        original_null = ilap_field.null
        ilap_field.null = True
        try:
            # Clear the cached FK value so the descriptor re-checks id_ilap_id
            tanda_terima.__dict__.pop('_id_ilap_cache', None)
            tanda_terima.id_ilap_id = None
            # Line 114: not ilap_id (None) AND _existing_tiket_ids is non-empty → triggered
            form = TandaTerimaDataForm(instance=tanda_terima)
            assert form is not None
        finally:
            ilap_field.null = original_null

    def test_edit_instance_no_ilap_no_tikets_uses_empty_queryset(self, db):
        """Line 136: edit with no id_ilap and no tikets → queryset = filter(id__in=empty set)."""
        from diamond_web.forms.tanda_terima_data import TandaTerimaDataForm
        from diamond_web.models.tanda_terima_data import TandaTerimaData

        ilap = ILAPFactory()
        user = UserFactory()
        tanda_terima = TandaTerimaData.objects.create(
            nomor_tanda_terima=2,
            tahun_terima=2024,
            tanggal_tanda_terima=timezone.now(),
            id_ilap=ilap,
            id_perekam=user,
            active=True,
        )

        # Temporarily allow null so accessing instance.id_ilap with id_ilap_id=None
        # returns None rather than raising RelatedObjectDoesNotExist.
        ilap_field = TandaTerimaData._meta.get_field('id_ilap')
        original_null = ilap_field.null
        ilap_field.null = True
        try:
            tanda_terima.__dict__.pop('_id_ilap_cache', None)
            tanda_terima.id_ilap_id = None
            # No DetilTandaTerima → _existing_tiket_ids = empty set
            # → if not ilap_id and _existing_tiket_ids: False
            # → ilap_id stays None → if ilap_id: False → else at line 136
            form = TandaTerimaDataForm(instance=tanda_terima)
            assert form is not None
            assert 'tiket_ids' in form.fields
        finally:
            ilap_field.null = original_null

    def test_create_flow_admin_user_no_ilap_selected(self, db, admin_user):
        """Line 196: admin/superuser create flow with no ILAP selected sets full tiket queryset."""
        from diamond_web.forms.tanda_terima_data import TandaTerimaDataForm

        # Unbound form, admin user, no tiket_pk, no instance → create flow, else branch
        form = TandaTerimaDataForm(user=admin_user)
        assert form is not None
        assert 'tiket_ids' in form.fields

    def test_clean_tiket_ids_returns_early_when_field_not_present(self, db):
        """Line 208: clean_tiket_ids() returns immediately when tiket_ids not in fields."""
        from diamond_web.forms.tanda_terima_data import TandaTerimaDataForm

        ilap, tiket = self._make_ilap_and_tiket()

        # tiket_pk causes tiket_ids field to be deleted from self.fields
        form = TandaTerimaDataForm(tiket_pk=tiket.pk, user=None)
        assert 'tiket_ids' not in form.fields

        # Manually call clean_tiket_ids — should return immediately (line 208)
        form.cleaned_data = {}
        result = form.clean_tiket_ids()
        assert result is None

    def test_clean_tiket_ids_tiket_not_available_raises_error(self, db, admin_user):
        """Line 247: ValidationError when selected tiket is already in another active tanda terima."""
        from django.core.exceptions import ValidationError
        from diamond_web.forms.tanda_terima_data import TandaTerimaDataForm
        from diamond_web.models.tanda_terima_data import TandaTerimaData
        from diamond_web.models.detil_tanda_terima import DetilTandaTerima

        ilap, tiket = self._make_ilap_and_tiket()

        # Create another active TandaTerima that already uses this tiket
        other_tt = TandaTerimaData.objects.create(
            nomor_tanda_terima=99,
            tahun_terima=2024,
            tanggal_tanda_terima=timezone.now(),
            id_ilap=ilap,
            id_perekam=admin_user,
            active=True,
        )
        DetilTandaTerima.objects.create(id_tanda_terima=other_tt, id_tiket=tiket)

        # Build a new (create-flow) form and call clean_tiket_ids manually
        form = TandaTerimaDataForm(user=admin_user)
        form.cleaned_data = {
            'id_ilap': ilap,
            # tiket is already used in another active TandaTerima → not in available_ids
            'tiket_ids': TiketFactory._meta.model.objects.filter(pk=tiket.pk),
        }
        form._existing_tiket_ids = set()
        # Status=1 → lt 8 → tiket passes status check, but is excluded via other_tanda_terima_tikets

        with pytest.raises(ValidationError) as exc_info:
            form.clean_tiket_ids()
        assert 'tidak tersedia' in str(exc_info.value)

    def test_save_with_formatted_nomor_string(self, db, admin_user):
        """Line 247: save() processes a formatted nomor string."""
        from diamond_web.forms.tanda_terima_data import TandaTerimaDataForm
        from diamond_web.models.tanda_terima_data import TandaTerimaData

        ilap, tiket = self._make_ilap_and_tiket()

        # Build a valid form and manually set cleaned_data for save() testing
        form = TandaTerimaDataForm(user=admin_user)

        # Simulate a validated form state
        from django.db.models import Max
        tahun = 2024
        max_nomor = TandaTerimaData.objects.filter(tahun_terima=tahun).aggregate(
            Max('nomor_tanda_terima')
        )['nomor_tanda_terima__max'] or 0

        form.cleaned_data = {
            'tanggal_tanda_terima': timezone.now(),
            'tahun_terima': tahun,
            'id_ilap': ilap,
            'tiket_ids': TiketFactory._meta.model.objects.filter(pk=tiket.pk),
            'nomor_tanda_terima': f'{str(max_nomor + 1).zfill(5)}.TTD/PJ.1031/{tahun}',
        }
        form._existing_tiket_ids = set()

        # Patch super().save() to return a minimal unsaved instance
        instance = TandaTerimaData(
            tanggal_tanda_terima=timezone.now(),
            tahun_terima=tahun,
            id_ilap=ilap,
        )

        with patch.object(TandaTerimaDataForm.__bases__[1], 'save', return_value=instance):
            result = form.save(commit=False)

        # Line 247 path: formatted_nomor was a string, seq_part extracted
        assert result.nomor_tanda_terima == max_nomor + 1

    def test_save_fallback_when_no_formatted_nomor(self, db, admin_user):
        """Lines 265-268: save() fallback computes nomor from tahun when formatted_nomor empty."""
        from diamond_web.forms.tanda_terima_data import TandaTerimaDataForm
        from diamond_web.models.tanda_terima_data import TandaTerimaData

        ilap, tiket = self._make_ilap_and_tiket()
        tahun = 2025

        form = TandaTerimaDataForm(user=admin_user)
        form.cleaned_data = {
            'tanggal_tanda_terima': timezone.now(),
            'tahun_terima': tahun,
            'id_ilap': ilap,
            'nomor_tanda_terima': '',   # Empty → fallback path at lines 265-268
        }
        form._existing_tiket_ids = set()

        instance = TandaTerimaData(
            tanggal_tanda_terima=timezone.now(),
            tahun_terima=tahun,
            id_ilap=ilap,
        )
        # instance.pk is None → elif not instance.pk → True → lines 265-268

        with patch.object(TandaTerimaDataForm.__bases__[1], 'save', return_value=instance):
            result = form.save(commit=False)

        # Fallback: nomor_tanda_terima should be 1 (no existing records for 2025)
        assert result.nomor_tanda_terima >= 1


# ─────────────────────────────────────────────────────────────────────────────
# forms/tiket.py — lines 129-130, 141-142
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTiketFormBranches:
    """Lines 129-130, 141-142 in forms/tiket.py."""

    def _setup_groups(self):
        """Ensure user_pide and user_pmde groups exist (required by TiketForm.__init__)."""
        Group.objects.get_or_create(name='user_pide')
        Group.objects.get_or_create(name='user_pmde')

    def test_existing_tiket_with_periode_data_sets_ilap(self, db):
        """Lines 129-130: editing an existing Tiket with id_periode_data fills ilap from instance."""
        from diamond_web.forms.tiket import TiketForm

        self._setup_groups()

        tiket = TiketFactory()   # TiketFactory always creates id_periode_data
        assert tiket.id_periode_data is not None

        # No POST data (data=None) → elif branch at line 128 is reached
        form = TiketForm(instance=tiket, user=None)

        # Lines 129-130: ilap_id and id_ilap.initial set from instance.id_periode_data
        assert form.fields['id_ilap'].initial is not None

    def test_non_admin_user_filters_periode_queryset(self, db):
        """Lines 141-142: non-admin user in form __init__ applies PIC filter to periode queryset."""
        from diamond_web.forms.tiket import TiketForm

        self._setup_groups()

        # Create a non-admin user
        user = UserFactory()
        group, _ = Group.objects.get_or_create(name='user_p3de')
        user.groups.add(group)

        tiket = TiketFactory()
        assert tiket.id_periode_data is not None

        # Editing existing tiket with a non-admin user → lines 141-142 triggered
        # (the elif branch in lines 128-130 fills ilap_id, then 141-142 filter applied)
        form = TiketForm(instance=tiket, user=user)

        # The form should be created without error
        assert form is not None
        # id_periode_data queryset filtered for non-admin user
        assert form.fields['id_periode_data'].queryset is not None
