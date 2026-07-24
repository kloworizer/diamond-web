"""Tests for editing a tiket's isian (EditTiketView / EditTiketForm).

A tiket may be edited only by its active P3DE PIC while it is in status
Direkam (1) and no tanda terima has been created yet. Once a tanda terima
exists the isian is locked.
"""
from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse

from diamond_web.models import Tiket, TiketPIC
from diamond_web.models.tiket_action import TiketAction
from diamond_web.constants.tiket_action_types import TiketActionType
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

    def test_surat_pengantar_fields_optional(self):
        tiket = TiketFactory(id_periode_data=_editable_periode_data())
        data = _valid_post(tiket)
        data.update({'nomor_surat_pengantar': '', 'nama_pengirim': '', 'tanggal_surat_pengantar': ''})
        form = EditTiketForm(data=data, instance=tiket)
        assert form.is_valid(), form.errors


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

    def test_button_hidden_for_non_pic_admin(self, client, admin_user):
        tiket = TiketFactory(status_tiket=1, id_periode_data=_editable_periode_data())
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_tiket'] is False
        assert b'Ubah Isian Tiket' not in resp.content
