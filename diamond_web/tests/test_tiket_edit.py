"""Tests for editing a tiket's isian (EditTiketView / EditTiketForm).

A tiket may be edited by its active P3DE PIC only while it is in status
Direkam (1) and no tanda terima has been created yet. Once a tanda terima
exists the isian is locked for the PIC.

P3DE administrators (`admin`, `admin_p3de`, superusers) are exempt from that
lock and may edit any tiket at any status; their edits are logged as DIUBAH
actions just like a PIC edit.
"""
from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse

from diamond_web.models import Tiket, TiketPIC
from diamond_web.models.tiket_action import TiketAction
from diamond_web.constants.tiket_action_types import TiketActionType
from diamond_web.constants.tiket_status import STATUS_LABELS
from diamond_web.forms.edit_tiket import EditTiketForm
from diamond_web.tests.conftest import (
    TiketFactory, TiketPICFactory, PICFactory, UserFactory,
    PeriodeJenisDataFactory,
)


def _editable_periode_data():
    """PeriodeJenisData whose end_date is far in the future so the DIP-date
    validation never trips on a random factory date."""
    return PeriodeJenisDataFactory(end_date=date(2099, 12, 31))


def _past_dip():
    """A tgl_terima_dip value safely in the past (datetime-local format)."""
    return (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')


def _valid_post(tiket, **overrides):
    data = {
        'periode': tiket.periode,
        'tahun': tiket.tahun,
        'penyampaian': tiket.penyampaian,
        'id_bentuk_data': tiket.id_bentuk_data_id,
        'id_cara_penyampaian': tiket.id_cara_penyampaian_id,
        'baris_diterima': tiket.baris_diterima,
        'tgl_terima_dip': _past_dip(),
    }
    data.update(overrides)
    return data


def _status_penelitian(deskripsi):
    from diamond_web.models.status_penelitian import StatusPenelitian
    status, _ = StatusPenelitian.objects.get_or_create(deskripsi=deskripsi)
    return status


def _days_ago(days):
    return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')


def _active_p3de_tiket(user, status=1, tanda_terima=False):
    tiket = TiketFactory(
        status_tiket=status,
        tanda_terima=tanda_terima,
        id_periode_data=_editable_periode_data(),
    )
    TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE, active=True)
    PICFactory(
        tipe='P3DE',
        id_sub_jenis_data_ilap=tiket.id_periode_data.id_sub_jenis_data_ilap,
        id_user=user,
        end_date=None,
    )
    return tiket


# ============================================================
# EditTiketForm
# ============================================================

@pytest.mark.django_db
class TestEditTiketForm:

    def test_valid_submission(self):
        tiket = TiketFactory(id_periode_data=_editable_periode_data())
        form = EditTiketForm(data=_valid_post(tiket), instance=tiket)
        assert form.is_valid(), form.errors

    def test_periode_data_not_in_fields(self):
        """ILAP / jenis data must not be editable through this form."""
        form = EditTiketForm(instance=TiketFactory())
        assert 'id_periode_data' not in form.fields
        assert 'status_ketersediaan_data' not in form.fields

    def test_future_tgl_terima_dip_rejected(self):
        tiket = TiketFactory(id_periode_data=_editable_periode_data())
        future = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        form = EditTiketForm(data=_valid_post(tiket, tgl_terima_dip=future), instance=tiket)
        assert not form.is_valid()
        assert 'tgl_terima_dip' in form.errors

    def test_dip_before_vertikal_rejected(self):
        tiket = TiketFactory(id_periode_data=_editable_periode_data())
        vertikal = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        dip = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%dT%H:%M')
        form = EditTiketForm(
            data=_valid_post(tiket, tgl_terima_vertikal=vertikal, tgl_terima_dip=dip),
            instance=tiket,
        )
        assert not form.is_valid()

    def test_dip_after_end_date_rejected(self):
        tiket = TiketFactory(id_periode_data=PeriodeJenisDataFactory(end_date=date(2000, 1, 1)))
        form = EditTiketForm(data=_valid_post(tiket), instance=tiket)
        assert not form.is_valid()

    def test_bentuk_data_excludes_tidak_tersedia(self):
        from diamond_web.models.bentuk_data import BentukData
        tidak_tersedia, _ = BentukData.objects.get_or_create(deskripsi='Data Tidak Tersedia')
        tiket = TiketFactory()  # its own bentuk data is a normal (available) one
        form = EditTiketForm(instance=tiket)
        qs = form.fields['id_bentuk_data'].queryset
        assert tidak_tersedia not in qs
        assert not qs.filter(deskripsi__icontains='tidak tersedia').exists()
        assert tiket.id_bentuk_data in qs

    def test_current_bentuk_data_stays_selectable(self):
        """A "data tidak tersedia" tiket (admin-editable) keeps its own value.

        Without this the admin could not save the form at all without also
        changing the bentuk data.
        """
        from diamond_web.models.bentuk_data import BentukData
        tidak_tersedia, _ = BentukData.objects.get_or_create(deskripsi='Data Tidak Tersedia')
        tiket = TiketFactory(
            id_bentuk_data=tidak_tersedia, id_periode_data=_editable_periode_data()
        )
        assert tidak_tersedia in EditTiketForm(instance=tiket).fields['id_bentuk_data'].queryset
        form = EditTiketForm(data=_valid_post(tiket), instance=tiket)
        assert form.is_valid(), form.errors

    def test_surat_pengantar_fields_optional(self):
        tiket = TiketFactory(id_periode_data=_editable_periode_data())
        data = _valid_post(tiket)
        data.update({'nomor_surat_pengantar': '', 'nama_pengirim': '', 'tanggal_surat_pengantar': ''})
        form = EditTiketForm(data=data, instance=tiket)
        assert form.is_valid(), form.errors


# ============================================================
# EditTiketForm — admin-only workflow isian
# ============================================================

@pytest.mark.django_db
class TestEditTiketFormAdminFields:
    """The later workflow isian is editable by P3DE admins only."""

    ADMIN_FIELDS = [
        'tgl_teliti', 'baris_lengkap', 'baris_tidak_lengkap',
        'tgl_nadine', 'nomor_nd_nadine', 'tgl_kirim_pide',
    ]

    def _tiket(self, **kwargs):
        # Dikirim ke PIDE by default: both admin sections are shown only for a
        # tiket that has been through those steps.
        kwargs.setdefault('status_tiket', 4)
        kwargs.setdefault('id_periode_data', _editable_periode_data())
        kwargs.setdefault('baris_diterima', 100)
        kwargs.setdefault('tgl_terima_dip', datetime.now() - timedelta(days=10))
        return TiketFactory(**kwargs)

    def _penelitian_post(self, tiket, **overrides):
        data = _valid_post(
            tiket,
            baris_diterima=tiket.baris_diterima,
            # Older than every tgl_teliti used below, so only the case under
            # test can trip the "teliti before terima DIP" rule.
            tgl_terima_dip=(datetime.now() - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M'),
            tgl_teliti=_days_ago(5),
            baris_lengkap=tiket.baris_diterima,
            baris_tidak_lengkap=0,
        )
        data.update(overrides)
        return data

    def _full_post(self, tiket, **overrides):
        """A post that fills both admin groups with consistent values."""
        data = self._penelitian_post(
            tiket,
            tgl_nadine=_days_ago(3),
            nomor_nd_nadine='ND-123',
            tgl_kirim_pide=_days_ago(2),
        )
        data.update(overrides)
        return data

    def _recorded_tiket(self, status):
        """A tiket that has been through penelitian and pengiriman ke PIDE."""
        return self._tiket(
            status_tiket=status,
            tgl_teliti=datetime.now() - timedelta(days=5),
            baris_lengkap=100,
            baris_tidak_lengkap=0,
            id_status_penelitian=_status_penelitian('Lengkap'),
            tgl_nadine=datetime.now() - timedelta(days=3),
            nomor_nd_nadine='ND-123',
            tgl_kirim_pide=datetime.now() - timedelta(days=2),
        )

    def test_fields_hidden_for_pic(self):
        form = EditTiketForm(instance=self._tiket())
        for name in self.ADMIN_FIELDS:
            assert name not in form.fields

    def test_fields_present_for_admin(self):
        form = EditTiketForm(instance=self._tiket(), is_admin=True)
        assert form.show_penelitian is True
        assert form.show_pengiriman_pide is True
        for name in self.ADMIN_FIELDS:
            assert name in form.fields
            assert form.fields[name].required is False

    @pytest.mark.parametrize('status,penelitian,pengiriman', [
        (1, False, False),   # Direkam — neither step has happened
        (2, True, False),    # Diteliti — penelitian only
        (3, True, False),    # Dikembalikan — never sent to PIDE
        (4, True, True),     # Dikirim ke PIDE
        (5, True, True),
        (6, True, True),
        (7, True, True),
        (8, True, True),
    ])
    def test_sections_follow_the_workflow_step(self, status, penelitian, pengiriman):
        """A section only exists for a step the tiket has been through, so an
        edit can never write isian that contradicts the status."""
        form = EditTiketForm(instance=self._tiket(status_tiket=status), is_admin=True)
        assert form.show_penelitian is penelitian
        assert form.show_pengiriman_pide is pengiriman
        for name in ('tgl_teliti', 'baris_lengkap', 'baris_tidak_lengkap'):
            assert (name in form.fields) is penelitian
        for name in ('tgl_nadine', 'nomor_nd_nadine', 'tgl_kirim_pide'):
            assert (name in form.fields) is pengiriman

    def test_direkam_edit_keeps_hasil_penelitian_untouched(self):
        """The hidden fields are absent, so a save must not null them."""
        tiket = self._tiket(
            status_tiket=1,
            baris_lengkap=100,
            baris_tidak_lengkap=0,
            tgl_teliti=datetime.now() - timedelta(days=5),
            id_status_penelitian=_status_penelitian('Lengkap'),
        )
        form = EditTiketForm(
            data=self._full_post(tiket, nama_pengirim='Dikoreksi'),
            instance=tiket,
            is_admin=True,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.baris_lengkap == 100
        assert saved.tgl_teliti is not None
        assert saved.id_status_penelitian.deskripsi == 'Lengkap'

    def test_diteliti_edit_keeps_pengiriman_pide_untouched(self):
        tiket = self._tiket(
            status_tiket=2,
            baris_lengkap=100,
            baris_tidak_lengkap=0,
            tgl_teliti=datetime.now() - timedelta(days=5),
            tgl_nadine=datetime.now() - timedelta(days=3),
            nomor_nd_nadine='ND-123',
            tgl_kirim_pide=datetime.now() - timedelta(days=2),
        )
        form = EditTiketForm(
            data=self._full_post(tiket, nama_pengirim='Dikoreksi'),
            instance=tiket,
            is_admin=True,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.nomor_nd_nadine == 'ND-123'
        assert saved.tgl_nadine is not None
        assert saved.tgl_kirim_pide is not None

    def test_pic_post_cannot_set_admin_fields(self):
        """Posting the extra isian as a PIC is ignored, not applied."""
        tiket = self._tiket()
        form = EditTiketForm(data=self._penelitian_post(tiket), instance=tiket)
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.tgl_teliti is None
        assert saved.baris_lengkap is None
        assert saved.id_status_penelitian is None

    def test_admin_saves_hasil_penelitian(self):
        _status_penelitian('Lengkap')
        tiket = self._tiket()
        form = EditTiketForm(data=self._penelitian_post(tiket), instance=tiket, is_admin=True)
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.tgl_teliti is not None
        assert saved.baris_lengkap == 100
        assert saved.baris_tidak_lengkap == 0
        assert saved.id_status_penelitian.deskripsi == 'Lengkap'

    @pytest.mark.parametrize('baris_lengkap,deskripsi', [
        (100, 'Lengkap'),
        (40, 'Lengkap Sebagian'),
        (0, 'Tidak Lengkap'),
    ])
    def test_status_penelitian_auto_calculated(self, baris_lengkap, deskripsi):
        _status_penelitian(deskripsi)
        tiket = self._tiket()
        form = EditTiketForm(
            data=self._penelitian_post(
                tiket,
                baris_lengkap=baris_lengkap,
                baris_tidak_lengkap=tiket.baris_diterima - baris_lengkap,
            ),
            instance=tiket,
            is_admin=True,
        )
        assert form.is_valid(), form.errors
        assert form.save().id_status_penelitian.deskripsi == deskripsi

    def test_status_penelitian_follows_edited_baris_diterima(self):
        """The check uses the submitted baris diterima, not the stored one."""
        _status_penelitian('Lengkap')
        tiket = self._tiket()
        form = EditTiketForm(
            data=self._penelitian_post(
                tiket, baris_diterima=60, baris_lengkap=60, baris_tidak_lengkap=0
            ),
            instance=tiket,
            is_admin=True,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.baris_diterima == 60
        assert saved.id_status_penelitian.deskripsi == 'Lengkap'

    def test_baris_sum_must_match_baris_diterima(self):
        tiket = self._tiket()
        form = EditTiketForm(
            data=self._penelitian_post(tiket, baris_lengkap=30, baris_tidak_lengkap=30),
            instance=tiket,
            is_admin=True,
        )
        assert not form.is_valid()
        assert 'baris_diterima' in form.errors

    def test_edited_baris_diterima_must_match_baris_sum(self):
        """Changing baris diterima alone breaks the identity."""
        tiket = self._tiket()
        form = EditTiketForm(
            data=self._penelitian_post(tiket, baris_diterima=80),
            instance=tiket,
            is_admin=True,
        )
        assert not form.is_valid()
        assert 'baris_diterima' in form.errors

    def test_pic_edit_keeps_baris_diterima_identity(self):
        """A PIC has no baris lengkap fields but still cannot break the sum."""
        tiket = self._tiket(status_tiket=2, baris_lengkap=60, baris_tidak_lengkap=40)
        form = EditTiketForm(data=_valid_post(tiket, baris_diterima=90), instance=tiket)
        assert not form.is_valid()
        assert 'baris_diterima' in form.errors

        form = EditTiketForm(data=_valid_post(tiket, baris_diterima=100), instance=tiket)
        assert form.is_valid(), form.errors

    def test_baris_values_without_tgl_teliti_accepted(self):
        """Old-DB tikets carry baris lengkap values with no tanggal teliti."""
        tiket = self._tiket()
        data = self._penelitian_post(tiket)
        data['tgl_teliti'] = ''
        form = EditTiketForm(data=data, instance=tiket, is_admin=True)
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.tgl_teliti is None
        assert saved.baris_lengkap == tiket.baris_diterima

    def test_baris_values_must_be_filled_as_a_pair(self):
        """Either half alone cannot add up to baris diterima."""
        tiket = self._tiket()
        data = self._penelitian_post(tiket)
        data['baris_tidak_lengkap'] = ''
        form = EditTiketForm(data=data, instance=tiket, is_admin=True)
        assert not form.is_valid()
        assert 'baris_tidak_lengkap' in form.errors

    def test_tgl_teliti_before_tgl_terima_dip_rejected(self):
        tiket = self._tiket()
        form = EditTiketForm(
            data=self._penelitian_post(tiket, tgl_teliti=_days_ago(30)),
            instance=tiket,
            is_admin=True,
        )
        assert not form.is_valid()
        assert 'tgl_teliti' in form.errors

    def test_future_tgl_teliti_rejected(self):
        tiket = self._tiket()
        future = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        form = EditTiketForm(
            data=self._penelitian_post(tiket, tgl_teliti=future),
            instance=tiket,
            is_admin=True,
        )
        assert not form.is_valid()
        assert 'tgl_teliti' in form.errors

    def test_admin_saves_pengiriman_pide(self):
        _status_penelitian('Lengkap')
        tiket = self._tiket()
        form = EditTiketForm(
            data=self._penelitian_post(
                tiket,
                tgl_nadine=_days_ago(3),
                nomor_nd_nadine='ND-123',
                tgl_kirim_pide=_days_ago(2),
            ),
            instance=tiket,
            is_admin=True,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.nomor_nd_nadine == 'ND-123'
        assert saved.tgl_nadine is not None
        assert saved.tgl_kirim_pide is not None

    def test_partial_pengiriman_pide_accepted(self):
        """Migrated tikets carry the trio partially; an edit must not demand
        values the workflow never recorded."""
        tiket = self._tiket()
        form = EditTiketForm(
            data=self._penelitian_post(tiket, nomor_nd_nadine='ND-123'),
            instance=tiket,
            is_admin=True,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.nomor_nd_nadine == 'ND-123'
        assert saved.tgl_nadine is None

    def test_tgl_nadine_before_tgl_teliti_rejected(self):
        tiket = self._tiket()
        form = EditTiketForm(
            data=self._penelitian_post(
                tiket,
                tgl_teliti=_days_ago(3),
                tgl_nadine=_days_ago(4),
                nomor_nd_nadine='ND-123',
                tgl_kirim_pide=_days_ago(1),
            ),
            instance=tiket,
            is_admin=True,
        )
        assert not form.is_valid()
        assert 'tgl_nadine' in form.errors

    @pytest.mark.parametrize('status', [2, 4, 5, 6])
    def test_hasil_penelitian_cannot_be_nulled_by_status(self, status):
        tiket = self._recorded_tiket(status)
        form = EditTiketForm(
            data=self._full_post(
                tiket, tgl_teliti='', baris_lengkap='', baris_tidak_lengkap=''
            ),
            instance=tiket,
            is_admin=True,
        )
        assert not form.is_valid()
        for name in ('tgl_teliti', 'baris_lengkap', 'baris_tidak_lengkap'):
            assert 'tidak boleh dikosongkan' in str(form.errors[name])

    @pytest.mark.parametrize('status', [4, 5, 6])
    def test_pengiriman_pide_cannot_be_nulled_by_status(self, status):
        tiket = self._recorded_tiket(status)
        form = EditTiketForm(
            data=self._full_post(
                tiket, tgl_nadine='', nomor_nd_nadine='', tgl_kirim_pide=''
            ),
            instance=tiket,
            is_admin=True,
        )
        assert not form.is_valid()
        for name in ('tgl_nadine', 'nomor_nd_nadine', 'tgl_kirim_pide'):
            assert 'tidak boleh dikosongkan' in str(form.errors[name])
        # The message names the status that blocks the change.
        assert STATUS_LABELS[status] in str(form.errors['tgl_nadine'])

    def test_locked_isian_can_still_be_corrected(self):
        tiket = self._recorded_tiket(4)
        form = EditTiketForm(
            data=self._full_post(tiket, nomor_nd_nadine='ND-KOREKSI'),
            instance=tiket,
            is_admin=True,
        )
        assert form.is_valid(), form.errors
        assert form.save().nomor_nd_nadine == 'ND-KOREKSI'

    @pytest.mark.parametrize('status', [4, 5, 6, 7, 8])
    def test_only_recorded_isian_is_protected(self, status):
        """The guard blocks nulling, it never demands a value that was never
        recorded — plenty of migrated tikets are past a step without one."""
        recorded = self._recorded_tiket(status)
        form = EditTiketForm(
            data=self._full_post(
                recorded, tgl_nadine='', nomor_nd_nadine='', tgl_kirim_pide=''
            ),
            instance=recorded,
            is_admin=True,
        )
        assert not form.is_valid()
        assert 'tgl_nadine' in form.errors

        # Same status, but the tiket never recorded a pengiriman or a tgl
        # teliti: the edit must go through without inventing them.
        incomplete = self._tiket(status_tiket=status, baris_lengkap=100, baris_tidak_lengkap=0)
        form = EditTiketForm(
            data=self._penelitian_post(incomplete, tgl_teliti=''),
            instance=incomplete,
            is_admin=True,
        )
        assert form.is_valid(), form.errors

    def test_old_db_direkam_tiket_saves_unchanged(self):
        """Regression: old-DB tikets sit in Direkam with zeroed baris values
        and no tanggal teliti, which must not be read as a hasil penelitian."""
        tiket = self._tiket(
            status_tiket=1, baris_diterima=0, baris_lengkap=0, baris_tidak_lengkap=0,
            old_db=True,
        )
        form = EditTiketForm(
            data=_valid_post(tiket, baris_diterima=0, baris_lengkap=0, baris_tidak_lengkap=0),
            instance=tiket,
            is_admin=True,
        )
        assert form.is_valid(), form.errors

    def test_direkam_baris_diterima_correctable(self):
        """At Direkam there is no hasil penelitian to stay consistent with, so
        baris diterima may be corrected on its own."""
        tiket = self._tiket(
            status_tiket=1, baris_diterima=0, baris_lengkap=0, baris_tidak_lengkap=0,
            old_db=True,
        )
        for form in (
            EditTiketForm(data=_valid_post(tiket, baris_diterima=500), instance=tiket),
            EditTiketForm(
                data=_valid_post(
                    tiket, baris_diterima=500, baris_lengkap=0, baris_tidak_lengkap=0
                ),
                instance=tiket,
                is_admin=True,
            ),
        ):
            assert form.is_valid(), form.errors

    def test_untouched_legacy_chronology_does_not_block_edit(self):
        """Migrated tikets carry tgl nadine before tgl teliti; correcting an
        unrelated field must not be blocked by data the admin did not write."""
        tiket = self._tiket(
            status_tiket=4,
            tgl_teliti=datetime.now() - timedelta(days=3),
            baris_lengkap=100,
            baris_tidak_lengkap=0,
            tgl_nadine=datetime.now() - timedelta(days=9),
            nomor_nd_nadine='ND-LAMA',
            tgl_kirim_pide=datetime.now() - timedelta(days=8),
        )
        data = self._full_post(
            tiket,
            tgl_teliti=_days_ago(3),
            tgl_nadine=_days_ago(9),
            nomor_nd_nadine='ND-BARU',
            tgl_kirim_pide=_days_ago(8),
        )
        form = EditTiketForm(data=data, instance=tiket, is_admin=True)
        assert form.is_valid(), form.errors
        assert form.save().nomor_nd_nadine == 'ND-BARU'

        # Touching one of the two dates does subject the pair to the rule.
        data['tgl_nadine'] = _days_ago(10)
        form = EditTiketForm(data=data, instance=tiket, is_admin=True)
        assert not form.is_valid()
        assert 'tgl_nadine' in form.errors

    def test_tgl_kirim_pide_before_tgl_nadine_rejected(self):
        tiket = self._tiket()
        form = EditTiketForm(
            data=self._penelitian_post(
                tiket,
                tgl_nadine=_days_ago(2),
                nomor_nd_nadine='ND-123',
                tgl_kirim_pide=_days_ago(3),
            ),
            instance=tiket,
            is_admin=True,
        )
        assert not form.is_valid()
        assert 'tgl_kirim_pide' in form.errors


# ============================================================
# EditTiketView access control
# ============================================================

@pytest.mark.django_db
class TestEditTiketViewAccess:

    def test_requires_login(self, client, tiket):
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_denied_without_pic(self, client, authenticated_user, tiket):
        client.force_login(authenticated_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_get_form_as_active_p3de(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert resp.status_code == 200
        assert b'editTiketForm' in resp.content

    def test_denied_when_tanda_terima_exists(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user, tanda_terima=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_denied_when_status_not_direkam(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user, status=4)
        client.force_login(authenticated_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_ajax_denied_returns_json_403(self, client, authenticated_user, tiket):
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('edit_tiket', args=[tiket.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 403
        assert resp.json()['success'] is False


@pytest.mark.django_db
class TestEditTiketViewAdminP3DEAccess:
    """Admin P3DE may edit any tiket without being one of its PICs."""

    def test_allowed_without_pic(self, client, p3de_admin_user):
        tiket = TiketFactory(status_tiket=1, id_periode_data=_editable_periode_data())
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert resp.status_code == 200
        assert b'editTiketForm' in resp.content

    def test_allowed_when_tanda_terima_exists(self, client, p3de_admin_user):
        tiket = TiketFactory(
            status_tiket=1, tanda_terima=True, id_periode_data=_editable_periode_data()
        )
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert resp.status_code == 200

    @pytest.mark.parametrize('status', [4, 6, 7, 8])
    def test_allowed_at_any_status(self, client, p3de_admin_user, status):
        tiket = TiketFactory(status_tiket=status, id_periode_data=_editable_periode_data())
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_admin_allowed_when_locked(self, client, admin_user):
        """The global admin group keeps access under the same rules."""
        tiket = TiketFactory(
            status_tiket=4, tanda_terima=True, id_periode_data=_editable_periode_data()
        )
        client.force_login(admin_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_other_admin_role_still_denied(self, client, db):
        """admin_pide/admin_pmde are not P3DE administrators."""
        from django.contrib.auth.models import Group
        user = UserFactory()
        group, _ = Group.objects.get_or_create(name='admin_pide')
        user.groups.add(group)
        tiket = TiketFactory(status_tiket=1, id_periode_data=_editable_periode_data())
        client.force_login(user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_edit_is_logged_as_diubah_action(self, client, p3de_admin_user):
        """An admin edit lands in the audit trail exactly like a PIC edit."""
        tiket = TiketFactory(
            status_tiket=1, tanda_terima=True, id_periode_data=_editable_periode_data()
        )
        old_pengirim = tiket.nama_pengirim
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(tiket, nama_pengirim='Dikoreksi Admin'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200, resp.content
        tiket.refresh_from_db()
        assert tiket.nama_pengirim == 'Dikoreksi Admin'
        action = TiketAction.objects.filter(
            id_tiket=tiket, action=TiketActionType.DIUBAH
        ).latest('id')
        assert action.id_user == p3de_admin_user
        assert action.catatan.startswith('isian tiket diubah')
        assert f'{old_pengirim} → Dikoreksi Admin' in action.catatan

    def test_form_shows_workflow_isian(self, client, p3de_admin_user):
        tiket = TiketFactory(status_tiket=6, id_periode_data=_editable_periode_data())
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert b'id_edit_tgl_teliti' in resp.content
        assert b'id_edit_baris_lengkap' in resp.content
        assert b'id_edit_tgl_nadine' in resp.content
        assert b'name="nomor_nd_nadine"' in resp.content
        assert b'id_edit_tgl_kirim_pide' in resp.content
        assert b'edit-status-lengkap-sebagian' in resp.content

    @pytest.mark.parametrize('status,penelitian,pengiriman', [
        (1, False, False),
        (2, True, False),
        (4, True, True),
    ])
    def test_sections_rendered_per_status(self, client, p3de_admin_user, status,
                                          penelitian, pengiriman):
        tiket = TiketFactory(status_tiket=status, id_periode_data=_editable_periode_data())
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert (b'Hasil Penelitian' in resp.content) is penelitian
        assert (b'id_edit_tgl_teliti' in resp.content) is penelitian
        assert (b'Pengiriman ke PIDE' in resp.content) is pengiriman
        assert (b'id_edit_tgl_nadine' in resp.content) is pengiriman

    def test_pic_form_hides_workflow_isian(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('edit_tiket', args=[tiket.pk]))
        assert b'id_edit_tgl_teliti' not in resp.content
        assert b'id_edit_tgl_nadine' not in resp.content

    def test_admin_updates_workflow_isian(self, client, p3de_admin_user):
        _status_penelitian('Lengkap Sebagian')
        tiket = TiketFactory(
            status_tiket=6,
            baris_diterima=100,
            tgl_terima_dip=datetime.now() - timedelta(days=20),
            id_periode_data=_editable_periode_data(),
        )
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(
                tiket,
                baris_diterima=100,
                tgl_terima_dip=(datetime.now() - timedelta(days=20)).strftime('%Y-%m-%dT%H:%M'),
                tgl_teliti=_days_ago(5),
                baris_lengkap=60,
                baris_tidak_lengkap=40,
                tgl_nadine=_days_ago(3),
                nomor_nd_nadine='ND-999',
                tgl_kirim_pide=_days_ago(2),
            ),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200, resp.content
        tiket.refresh_from_db()
        assert tiket.baris_lengkap == 60
        assert tiket.baris_tidak_lengkap == 40
        assert tiket.nomor_nd_nadine == 'ND-999'
        assert tiket.tgl_teliti is not None
        assert tiket.tgl_kirim_pide is not None
        assert tiket.id_status_penelitian.deskripsi == 'Lengkap Sebagian'
        # An isian edit never moves the tiket through the workflow.
        assert tiket.status_tiket == 6
        action = TiketAction.objects.filter(
            id_tiket=tiket, action=TiketActionType.DIUBAH
        ).latest('id')
        assert 'Tanggal Teliti' in action.catatan

    def test_pic_cannot_post_workflow_isian(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(tiket, tgl_teliti=_days_ago(1), baris_lengkap=1, nomor_nd_nadine='ND-1'),
        )
        tiket.refresh_from_db()
        assert tiket.tgl_teliti is None
        assert tiket.baris_lengkap is None
        assert tiket.nomor_nd_nadine is None

    def test_edit_does_not_change_status(self, client, p3de_admin_user):
        tiket = TiketFactory(status_tiket=1, id_periode_data=_editable_periode_data())
        client.force_login(p3de_admin_user)
        client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(tiket, nama_pengirim='Tetap Direkam', status_tiket=4),
        )
        tiket.refresh_from_db()
        assert tiket.status_tiket == 1

    def test_workflow_isian_cannot_be_nulled_by_status(self, client, p3de_admin_user):
        """The status guard also applies to a posted request, not just the form."""
        tiket = TiketFactory(
            status_tiket=4,
            baris_diterima=100,
            baris_lengkap=100,
            baris_tidak_lengkap=0,
            tgl_terima_dip=datetime.now() - timedelta(days=20),
            tgl_teliti=datetime.now() - timedelta(days=5),
            tgl_nadine=datetime.now() - timedelta(days=3),
            nomor_nd_nadine='ND-123',
            tgl_kirim_pide=datetime.now() - timedelta(days=2),
            id_periode_data=_editable_periode_data(),
        )
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(tiket, baris_diterima=100),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 400
        assert 'tidak boleh dikosongkan' in resp.json()['message']
        tiket.refresh_from_db()
        assert tiket.nomor_nd_nadine == 'ND-123'
        assert tiket.tgl_teliti is not None


# ============================================================
# EditTiketView submission
# ============================================================

@pytest.mark.django_db
class TestEditTiketViewSubmit:

    def test_updates_fields(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(tiket, nama_pengirim='Budi Baru', baris_diterima=777),
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.nama_pengirim == 'Budi Baru'
        assert tiket.baris_diterima == 777

    def test_ajax_post_returns_json(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(tiket, nama_pengirim='Via Ajax'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        assert resp.json()['success'] is True
        tiket.refresh_from_db()
        assert tiket.nama_pengirim == 'Via Ajax'

    def test_records_diubah_action(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        client.post(reverse('edit_tiket', args=[tiket.pk]), _valid_post(tiket))
        assert TiketAction.objects.filter(
            id_tiket=tiket, action=TiketActionType.DIUBAH
        ).exists()

    def test_catatan_includes_changed_field_detail(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        old_pengirim = tiket.nama_pengirim
        client.force_login(authenticated_user)
        client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(tiket, nama_pengirim='Budi Baru', baris_diterima=777),
        )
        action = TiketAction.objects.filter(
            id_tiket=tiket, action=TiketActionType.DIUBAH
        ).latest('id')
        assert action.catatan.startswith('isian tiket diubah')
        # Reports the change as "<Field>: <old> → <new>"
        assert 'Nama Pengirim' in action.catatan
        assert f'{old_pengirim} → Budi Baru' in action.catatan
        assert 'Baris Diterima' in action.catatan
        assert '→ 777' in action.catatan

    def test_catatan_within_field_length(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        max_len = TiketAction._meta.get_field('catatan').max_length
        client.force_login(authenticated_user)
        client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(
                tiket,
                nomor_surat_pengantar='X' * 80,
                nama_pengirim='Y' * 50,
                baris_diterima=999999,
            ),
        )
        action = TiketAction.objects.filter(
            id_tiket=tiket, action=TiketActionType.DIUBAH
        ).latest('id')
        assert len(action.catatan) <= max_len

    def test_ajax_invalid_returns_json_400(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        future = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        resp = client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(tiket, tgl_terima_dip=future),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 400
        assert resp.json()['success'] is False

    def test_does_not_change_status(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        client.post(
            reverse('edit_tiket', args=[tiket.pk]),
            _valid_post(tiket, status_tiket=7),
        )
        tiket.refresh_from_db()
        assert tiket.status_tiket == 1


# ============================================================
# Detail page integration
# ============================================================

@pytest.mark.django_db
class TestEditButtonOnDetailPage:

    def test_button_visible_for_active_p3de_direkam(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_tiket'] is True
        assert b'editTiketModal' in resp.content

    def test_button_hidden_when_tanda_terima(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user, tanda_terima=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_tiket'] is False
        assert b'Ubah Isian Tiket' not in resp.content

    def test_button_hidden_when_not_direkam(self, client, authenticated_user):
        tiket = _active_p3de_tiket(authenticated_user, status=4)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_tiket'] is False

    def test_button_visible_for_non_pic_admin(self, client, admin_user):
        tiket = TiketFactory(status_tiket=1, id_periode_data=_editable_periode_data())
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_tiket'] is True
        assert b'Ubah Isian Tiket' in resp.content

    def test_button_hidden_for_non_pic_kasi(self, client, db):
        """Kasi see the tiket read-only; they get no edit button."""
        from django.contrib.auth.models import Group
        user = UserFactory()
        group, _ = Group.objects.get_or_create(name='kasi_p3de')
        user.groups.add(group)
        tiket = TiketFactory(status_tiket=1, id_periode_data=_editable_periode_data())
        client.force_login(user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_tiket'] is False
        assert b'Ubah Isian Tiket' not in resp.content


@pytest.mark.django_db
class TestAdminP3DEOnDetailPage:
    """Admin P3DE can open any tiket detail and always sees the edit button."""

    def test_can_open_detail_without_pic(self, client, p3de_admin_user):
        tiket = TiketFactory(status_tiket=1, id_periode_data=_editable_periode_data())
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200

    @pytest.mark.parametrize('status,tanda_terima', [(1, True), (4, False), (8, True)])
    def test_button_visible_regardless_of_state(self, client, p3de_admin_user, status, tanda_terima):
        tiket = TiketFactory(
            status_tiket=status,
            tanda_terima=tanda_terima,
            id_periode_data=_editable_periode_data(),
        )
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_tiket'] is True
        assert resp.context['user_is_admin_p3de'] is True
        assert b'Ubah Isian Tiket' in resp.content
        assert b'editTiketModal' in resp.content

    def test_non_p3de_admin_cannot_open_detail(self, client, db):
        from django.contrib.auth.models import Group
        user = UserFactory()
        group, _ = Group.objects.get_or_create(name='admin_pmde')
        user.groups.add(group)
        tiket = TiketFactory(status_tiket=1, id_periode_data=_editable_periode_data())
        client.force_login(user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code in (302, 403)
