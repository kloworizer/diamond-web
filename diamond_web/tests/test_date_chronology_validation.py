"""Chronological date/datetime validation across the tiket workflow and the
DateField-only "start_date/end_date" master-data forms.

The tiket workflow date fields are all DateTimeField columns fed by a
date-only <input type="date">; every clean_<field>() stamps the current
server time in via combine_date_with_current_time() so the stored value is
never midnight, and each step's date must not be earlier than the previous
step's stored date. This file tests each link in that chain, plus the
"start_date must not be after end_date" rule for the pure-DateField forms
(PIC, Durasi Jatuh Tempo, Periode Jenis Data, Jenis Prioritas Data,
Dasar Hukum).
"""
import pytest
from datetime import date, datetime, timedelta

from django.utils import timezone

from diamond_web.tests.conftest import (
    UserFactory,
    ILAPFactory,
    JenisDataILAPFactory,
    PeriodeJenisDataFactory,
    TiketFactory,
    TandaTerimaDataFactory,
    DasarHukumFactory,
    PICFactory,
    DurasiJatuhTempoFactory,
    JenisPrioritasDataFactory,
)
from diamond_web.models.detil_tanda_terima import DetilTandaTerima
from diamond_web.forms.rekam_hasil_penelitian import RekamHasilPenelitianForm
from diamond_web.forms.tanda_terima_data import TandaTerimaDataForm
from diamond_web.forms.dasar_hukum import DasarHukumForm
from diamond_web.forms.pic import PICForm
from diamond_web.forms.durasi_jatuh_tempo import DurasiJatuhTempoForm
from diamond_web.forms.periode_jenis_data import PeriodeJenisDataForm
from diamond_web.forms.jenis_prioritas_data import JenisPrioritasDataForm
from diamond_web.utils import combine_date_with_current_time


# --------------------------------------------------------------------------- #
# combine_date_with_current_time: every workflow date is stamped with "now",
# never midnight.
# --------------------------------------------------------------------------- #
class TestCombineDateWithCurrentTime:
    def test_replaces_time_of_day_with_now(self):
        value = datetime(2020, 1, 1, 0, 0, 0)
        result = combine_date_with_current_time(value)
        now = datetime.now()
        assert result.date() == date(2020, 1, 1)
        assert result.hour == now.hour
        assert result.minute == now.minute
        # Not midnight (the whole point of the helper).
        assert not (result.hour == 0 and result.minute == 0 and result.second == 0)

    def test_none_passthrough(self):
        assert combine_date_with_current_time(None) is None


# --------------------------------------------------------------------------- #
# Tanda Terima: must not be before the tiket's tgl_terima_dip.
# --------------------------------------------------------------------------- #
class TestTandaTerimaChronology:
    def test_tanggal_before_tgl_terima_dip_rejected(self, db):
        tiket = TiketFactory(status_tiket=1, tgl_terima_dip=timezone.now())
        ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        past_date = (timezone.now() - timedelta(days=5)).strftime('%Y-%m-%d')

        form = TandaTerimaDataForm(
            data={
                'tanggal_tanda_terima': past_date,
                'tahun_terima': str(timezone.now().year - 5),
                'id_ilap': ilap.pk,
                'tiket_ids': [str(tiket.pk)],
            },
            tiket_pk=None,
        )
        assert not form.is_valid()
        assert 'sebelum Tanggal Terima DIP' in str(form.errors)

    def test_tanggal_on_or_after_tgl_terima_dip_accepted(self, db):
        past = timezone.now() - timedelta(days=10)
        tiket = TiketFactory(status_tiket=1, tgl_terima_dip=past)
        ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        today = timezone.now().strftime('%Y-%m-%d')

        form = TandaTerimaDataForm(
            data={
                'tanggal_tanda_terima': today,
                'tahun_terima': str(timezone.now().year),
                'id_ilap': ilap.pk,
                'tiket_ids': [str(tiket.pk)],
            },
            tiket_pk=None,
        )
        is_valid = form.is_valid()
        assert is_valid, form.errors

    def test_single_tiket_flow_uses_tiket_pk(self, db):
        """When loaded from the tiket detail page (tiket_pk kwarg), tiket_ids
        is removed from the form entirely -- the chronology check must still
        run against that tiket via self.tiket_pk."""
        tiket = TiketFactory(status_tiket=1, tgl_terima_dip=timezone.now())
        ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        past_date = (timezone.now() - timedelta(days=3)).strftime('%Y-%m-%d')

        form = TandaTerimaDataForm(
            data={
                'tanggal_tanda_terima': past_date,
                'tahun_terima': str(timezone.now().year - 3),
                'id_ilap': ilap.pk,
            },
            tiket_pk=tiket.pk,
        )
        assert 'tiket_ids' not in form.fields
        assert not form.is_valid()
        assert 'sebelum Tanggal Terima DIP' in str(form.errors)


# --------------------------------------------------------------------------- #
# Rekam Hasil Penelitian: tgl_teliti must not be before tanggal_tanda_terima
# (the step immediately before it) -- this is the exact "tanggal teliti must
# be greater than the previous flow" rule.
# --------------------------------------------------------------------------- #
class TestRekamHasilPenelitianChronology:
    def _tiket_with_tanda_terima(self, tanda_terima_dt, tgl_terima_dip=None):
        tiket = TiketFactory(
            status_tiket=1,
            tgl_terima_dip=tgl_terima_dip or (tanda_terima_dt - timedelta(days=5)),
            baris_diterima=100,
        )
        ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        perekam = UserFactory()
        tanda_terima = TandaTerimaDataFactory(
            nomor_tanda_terima=987654,
            tahun_terima=tanda_terima_dt.year,
            tanggal_tanda_terima=tanda_terima_dt,
            id_ilap=ilap,
            id_perekam=perekam,
        )
        DetilTandaTerima.objects.create(id_tanda_terima=tanda_terima, id_tiket=tiket)
        return tiket

    def test_tgl_teliti_before_tanda_terima_rejected(self, db):
        tanda_terima_dt = timezone.now() - timedelta(days=2)
        tiket = self._tiket_with_tanda_terima(tanda_terima_dt)
        earlier = (tanda_terima_dt - timedelta(days=1)).strftime('%Y-%m-%d')

        form = RekamHasilPenelitianForm(
            data={
                'tgl_teliti': earlier,
                'baris_lengkap': '100',
                'baris_tidak_lengkap': '0',
            },
            instance=tiket,
        )
        assert not form.is_valid()
        assert 'sebelum Tanggal Tanda Terima' in str(form.errors)

    def test_tgl_teliti_on_or_after_tanda_terima_accepted(self, db):
        tanda_terima_dt = timezone.now() - timedelta(days=2)
        tiket = self._tiket_with_tanda_terima(tanda_terima_dt)
        today = timezone.now().strftime('%Y-%m-%d')

        form = RekamHasilPenelitianForm(
            data={
                'tgl_teliti': today,
                'baris_lengkap': '100',
                'baris_tidak_lengkap': '0',
            },
            instance=tiket,
        )
        assert form.is_valid(), form.errors

    def test_no_tanda_terima_row_skips_check_falls_back_to_tgl_terima_dip(self, db):
        """A tiket with no DetilTandaTerima row yet (shouldn't normally happen
        since Rekam Hasil Penelitian requires tanda terima first, but the
        form must not crash) still enforces the tgl_terima_dip check."""
        dip = timezone.now() - timedelta(days=5)
        tiket = TiketFactory(status_tiket=1, tgl_terima_dip=dip, baris_diterima=50)
        too_early = (dip - timedelta(days=1)).strftime('%Y-%m-%d')

        form = RekamHasilPenelitianForm(
            data={
                'tgl_teliti': too_early,
                'baris_lengkap': '50',
                'baris_tidak_lengkap': '0',
            },
            instance=tiket,
        )
        assert not form.is_valid()
        assert 'sebelum Tanggal Terima DIP' in str(form.errors)


# --------------------------------------------------------------------------- #
# Dasar Hukum: now renders type="date" and rejects end_date < start_date.
# --------------------------------------------------------------------------- #
class TestDasarHukumChronology:
    def test_widget_is_date_type(self):
        # Django's DateInput.__init__ pops 'type' out of attrs into
        # widget.input_type (used at render time to emit type="date") --
        # it is never present in .attrs itself.
        form = DasarHukumForm()
        assert form.fields['start_date'].widget.input_type == 'date'
        assert form.fields['end_date'].widget.input_type == 'date'

    def test_end_before_start_rejected(self, db):
        form = DasarHukumForm(data={
            'kategori': 'PMK',
            'deskripsi': 'Unique Dasar Hukum Test',
            'start_date': '2025-06-10',
            'end_date': '2025-06-01',
        })
        assert not form.is_valid()
        assert 'sebelum Tanggal Mulai' in str(form.errors)

    def test_end_after_start_accepted(self, db):
        form = DasarHukumForm(data={
            'kategori': 'PMK',
            'deskripsi': 'Unique Dasar Hukum Test 2',
            'start_date': '2025-06-01',
            'end_date': '2025-06-10',
        })
        assert form.is_valid(), form.errors


# --------------------------------------------------------------------------- #
# PIC / Durasi Jatuh Tempo / Periode Jenis Data / Jenis Prioritas Data:
# start_date must not be after end_date.
# --------------------------------------------------------------------------- #
class TestPICChronology:
    def test_end_before_start_rejected(self, db):
        sub_jenis = JenisDataILAPFactory()
        user = UserFactory()
        form = PICForm(data={
            'tipe': 'P3DE',
            'id_sub_jenis_data_ilap': sub_jenis.pk,
            'id_user': user.pk,
            'start_date': '2025-06-10',
            'end_date': '2025-06-01',
        })
        assert not form.is_valid()
        assert 'sebelum Tanggal Mulai' in str(form.errors)


class TestDurasiJatuhTempoChronology:
    def test_end_before_start_rejected(self, db):
        from django.contrib.auth.models import Group
        group, _ = Group.objects.get_or_create(name='user_pide')
        sub_jenis = JenisDataILAPFactory()
        form = DurasiJatuhTempoForm(
            data={
                'id_sub_jenis_data': sub_jenis.pk,
                'seksi': group.pk,
                'durasi': '5',
                'start_date': '2025-06-10',
                'end_date': '2025-06-01',
            },
            group_name='user_pide',
        )
        assert not form.is_valid()
        assert 'sebelum Tanggal Mulai' in str(form.errors)


class TestPeriodeJenisDataChronology:
    def test_end_before_start_rejected(self, db):
        sub_jenis = JenisDataILAPFactory()
        from diamond_web.tests.conftest import PeriodePengirimanFactory
        periode_pengiriman = PeriodePengirimanFactory()
        form = PeriodeJenisDataForm(data={
            'id_sub_jenis_data_ilap': sub_jenis.pk,
            'id_periode_pengiriman': periode_pengiriman.pk,
            'akhir_penyampaian': '10',
            'start_date': '2025-06-10',
            'end_date': '2025-06-01',
        })
        assert not form.is_valid()
        assert 'sebelum Tanggal Mulai' in str(form.errors)


class TestJenisPrioritasDataChronology:
    def test_end_before_start_rejected(self, db):
        sub_jenis = JenisDataILAPFactory()
        form = JenisPrioritasDataForm(data={
            'id_sub_jenis_data_ilap': sub_jenis.pk,
            'no_nd': 'ND-TEST-001',
            'tahun': '2025',
            'start_date': '2025-06-10',
            'end_date': '2025-06-01',
        })
        assert not form.is_valid()
        assert 'sebelum Tanggal Mulai' in str(form.errors)
