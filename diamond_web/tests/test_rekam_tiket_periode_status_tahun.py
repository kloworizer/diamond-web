"""Rekam Tiket: keterangan aktif/tidak aktif pada dropdown Jenis Data ILAP,
dan Tahun Data yang defaultnya kosong.

Periode Jenis Data yang sudah lewat end date tetap muncul di dropdown (data
yang diterima DIP sebelum end date masih boleh direkam), jadi labelnya harus
menyebut statusnya. Tahun Data dulu terisi tahun sekarang dan mudah terlewat
diganti; sekarang kosong dan wajib diisi.
"""
import json
from datetime import date, timedelta

import pytest
from django.urls import reverse

from diamond_web.forms.tiket import TiketForm
from diamond_web.models import Tiket
from diamond_web.models.periode_jenis_data import PeriodeJenisData
from diamond_web.tests.conftest import UserFactory, PeriodePengirimanFactory
from diamond_web.tests.test_rekam_tiket_gaps import (
    _build_tiket_post_data, _create_full_tiket_setup, _get_or_create_group,
)

TODAY = date(2026, 10, 1)


def _admin():
    admin = UserFactory(is_staff=True, is_superuser=True)
    admin.groups.add(_get_or_create_group('admin'))
    return admin


class TestStatusKeterangan:
    """PeriodeJenisData.status_keterangan — no DB needed."""

    def _pd(self, start, end=None):
        return PeriodeJenisData(start_date=start, end_date=end)

    def test_no_end_date_is_aktif(self):
        assert self._pd(date(2024, 1, 1)).status_keterangan(TODAY) == 'Aktif'

    def test_future_end_date_is_aktif_with_date(self):
        pd = self._pd(date(2024, 1, 1), date(2026, 12, 31))
        assert pd.status_keterangan(TODAY) == 'Aktif (s.d. 31-12-2026)'

    def test_end_date_today_is_still_aktif(self):
        pd = self._pd(date(2024, 1, 1), TODAY)
        assert pd.status_keterangan(TODAY) == 'Aktif (s.d. 01-10-2026)'

    def test_past_end_date_is_tidak_aktif(self):
        pd = self._pd(date(2024, 1, 1), date(2025, 12, 31))
        assert pd.status_keterangan(TODAY) == 'Tidak Aktif (end date 31-12-2025)'

    def test_future_start_is_belum_aktif(self):
        pd = self._pd(date(2027, 1, 1))
        assert pd.status_keterangan(TODAY) == 'Belum Aktif (mulai 01-01-2027)'


@pytest.mark.django_db
class TestJenisDataDropdownLabel:
    """Both label sources — the API used by the JS and the server-rendered form."""

    def _ended_and_active(self):
        jenis_data, active = _create_full_tiket_setup()
        ended = PeriodeJenisData.objects.create(
            id_sub_jenis_data_ilap=jenis_data,
            id_periode_pengiriman=PeriodePengirimanFactory(),
            start_date=date.today() - timedelta(days=730),
            end_date=date.today() - timedelta(days=10),
            akhir_penyampaian=30,
        )
        return jenis_data, active, ended

    def test_api_returns_status_keterangan(self, client):
        jenis_data, active, ended = self._ended_and_active()
        client.force_login(_admin())
        resp = client.get(reverse('api_ilap_periode_jenis_data', args=[jenis_data.id_ilap.pk]))
        rows = {r['id']: r for r in json.loads(resp.content)['data']}

        assert rows[active.pk]['status_keterangan'] == 'Aktif'
        end_str = ended.end_date.strftime('%d-%m-%Y')
        assert rows[ended.pk]['status_keterangan'] == f'Tidak Aktif (end date {end_str})'

    def test_form_label_shows_status(self):
        jenis_data, active, ended = self._ended_and_active()
        form = TiketForm(data={'id_ilap': jenis_data.id_ilap.pk}, user=_admin())
        labels = dict(form.fields['id_periode_data'].choices)

        assert labels[active.pk].endswith(' — Aktif')
        end_str = ended.end_date.strftime('%d-%m-%Y')
        assert labels[ended.pk].endswith(f' — Tidak Aktif (end date {end_str})')


@pytest.mark.django_db
class TestTahunDataDefaultKosong:

    def test_unbound_form_has_no_tahun_initial(self):
        form = TiketForm(user=_admin())
        assert form['tahun'].value() is None

    def test_rendered_select_starts_blank(self):
        form = TiketForm(user=_admin())
        html = str(form['tahun'])
        assert '<option value="" selected>---------</option>' in html
        assert f'<option value="{date.today().year}">' in html

    def test_tahun_is_required(self):
        assert TiketForm(user=_admin()).fields['tahun'].required is True

    def test_post_without_tahun_is_rejected(self, client):
        _, pd = _create_full_tiket_setup()
        post_data = _build_tiket_post_data(pd)
        post_data['status_ketersediaan_data'] = '1'
        post_data['tahun'] = ''

        client.force_login(_admin())
        resp = client.post(reverse('tiket_rekam_create'), post_data)

        assert resp.status_code == 200  # re-rendered, not redirected
        assert 'tahun' in resp.context['form'].errors
        assert not Tiket.objects.filter(id_periode_data=pd).exists()

    def test_post_with_tahun_still_creates_tiket(self, client):
        _, pd = _create_full_tiket_setup()
        post_data = _build_tiket_post_data(pd, year=date.today().year - 3)
        post_data['status_ketersediaan_data'] = '1'

        client.force_login(_admin())
        client.post(reverse('tiket_rekam_create'), post_data)

        created = Tiket.objects.get(id_periode_data=pd)
        assert created.tahun == date.today().year - 3
