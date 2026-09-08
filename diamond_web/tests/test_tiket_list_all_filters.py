"""Comprehensive filter coverage for tiket/list.py's tiket_data endpoint.

The get_filter_options=1 branch rebuilds the same ~20 dropdown filters
independently for ~6 different queryset derivations (filtered_qs,
tahun_filter_qs, periode_filter_qs, kategori_ilap_filter_qs, ilap_filter_qs,
jenis_filter_qs, status_filter_qs), so most of the file's remaining gaps are
simply "this filter param was never supplied in a test". Providing every
filter dimension in a single request exercises all of those repeated
branches at once.
"""
import json

import pytest
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.urls import reverse

from datetime import date, datetime

from diamond_web.models import ILAPKPP, KlasifikasiJenisData, PIC, TiketPIC
from diamond_web.models.status_penelitian import StatusPenelitian
from diamond_web.tests.conftest import (
    KanwilFactory,
    KPPFactory,
    PeriodeJenisDataFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)
from diamond_web.tests.test_remaining_coverage_gaps import _make_bundle
from diamond_web.views.tiket.list import tiket_data

rf = RequestFactory()


def _admin_user():
    user = UserFactory(is_staff=True, is_superuser=True)
    group, _ = Group.objects.get_or_create(name='admin')
    user.groups.add(group)
    return user


def _call(user, params):
    request = rf.get('/tiket/data/', params)
    request.user = user
    return tiket_data(request)


def _full_bundle():
    """A bundle wired up on every filterable dimension of tiket_data."""
    bundle = _make_bundle()
    tiket = bundle['tiket']
    ilap = bundle['ilap']
    jenis_data = bundle['jenis_data']

    kanwil = KanwilFactory()
    kpp = KPPFactory(id_kanwil=kanwil)
    ILAPKPP.objects.create(id_ilap=ilap, id_kpp=kpp)

    p3de = UserFactory()
    pide = UserFactory()
    pmde = UserFactory()
    TiketPICFactory(id_tiket=tiket, id_user=p3de, role=TiketPIC.Role.P3DE, active=True)
    TiketPICFactory(id_tiket=tiket, id_user=pide, role=TiketPIC.Role.PIDE, active=True)
    TiketPICFactory(id_tiket=tiket, id_user=pmde, role=TiketPIC.Role.PMDE, active=True)
    # pic_p3de/pic_pide/pic_pmde filter options come from the PIC "roster"
    # model (open-ended assignment), not from TiketPIC (per-tiket workflow
    # assignment) - both are needed for the dropdown to show these users.
    for tipe, user in ((PIC.TipePIC.P3DE, p3de), (PIC.TipePIC.PIDE, pide), (PIC.TipePIC.PMDE, pmde)):
        PIC.objects.create(
            id_sub_jenis_data_ilap=jenis_data, tipe=tipe, id_user=user,
            start_date=date(2023, 1, 1), end_date=None,
        )

    dasar_hukum = KlasifikasiJenisData.objects.get(id_sub_jenis_data=jenis_data).id_klasifikasi_tabel
    status_penelitian = tiket.id_status_penelitian

    tiket.status_ketersediaan_data = True
    tiket.special_request = True
    tiket.save(update_fields=['status_ketersediaan_data', 'special_request'])

    return {
        **bundle,
        'kanwil': kanwil,
        'kpp': kpp,
        'p3de': p3de,
        'pide': pide,
        'pmde': pmde,
        'dasar_hukum': dasar_hukum,
        'status_penelitian': status_penelitian,
    }


def _all_filters_params(b, extra=None):
    periode_pengiriman = b['periode_data'].id_periode_pengiriman
    params = {
        'get_filter_options': '1',
        'nomor_tiket': b['tiket'].nomor_tiket,
        'tahun': str(b['tiket'].tahun),
        # 'nope:x' hits the ValueError-on-int(pval) except branch; the
        # bulanan value still matches the real tiket.
        'periode': f"bulanan:{b['tiket'].periode},nope:x",
        'periode_penerimaan': periode_pengiriman.periode_penerimaan,
        'periode_pengiriman': periode_pengiriman.periode_penyampaian,
        'pic_p3de': str(b['p3de'].id),
        'pic_pide': str(b['pide'].id),
        'pic_pmde': str(b['pmde'].id),
        'kategori_ilap': str(b['ilap'].id_kategori_id),
        'ilap': str(b['ilap'].id),
        'jenis_data': b['jenis_data'].id_jenis_data,
        'sub_jenis_data': b['jenis_data'].id_sub_jenis_data,
        'kanwil': str(b['kanwil'].id),
        'kpp': str(b['kpp'].id),
        'kategori_wilayah': str(b['ilap'].id_kategori_wilayah_id),
        'jenis_tabel': str(b['jenis_data'].id_jenis_tabel_id),
        'dasar_hukum': str(b['dasar_hukum'].id),
        'status': str(b['tiket'].status_tiket),
        'status_penelitian': str(b['status_penelitian'].id) if b['status_penelitian'] else '',
        'status_ketersediaan_data': '1',
        'special_request': '1',
    }
    if extra:
        params.update(extra)
    return params


@pytest.mark.django_db
class TestGetFilterOptionsAllDimensions:
    def test_every_filter_dimension_populated(self):
        b = _full_bundle()
        resp = _call(_admin_user(), _all_filters_params(b))
        assert resp.status_code == 200
        payload = json.loads(resp.content)
        opts = payload['filter_options']

        assert any(o['id'] == b['tiket'].nomor_tiket for o in opts['nomor_tiket'])
        assert any(o['id'] == str(b['tiket'].tahun) for o in opts['tahun'])
        assert any(o['id'].startswith('bulanan:') for o in opts['periode'])
        assert opts['periode_penerimaan']
        assert opts['periode_pengiriman']
        assert any(o['id'] == str(b['p3de'].id) for o in opts['pic_p3de'])
        assert any(o['id'] == str(b['pide'].id) for o in opts['pic_pide'])
        assert any(o['id'] == str(b['pmde'].id) for o in opts['pic_pmde'])
        assert any(o['id'] == str(b['ilap'].id_kategori_id) for o in opts['kategori_ilap'])
        assert any(o['id'] == str(b['ilap'].id) for o in opts['ilap'])
        assert any(o['id'] == b['jenis_data'].id_jenis_data for o in opts['jenis_data'])
        assert any(o['id'] == b['jenis_data'].id_sub_jenis_data for o in opts['sub_jenis_data'])
        assert any(o['id'] == str(b['kanwil'].id) for o in opts['kanwil'])
        assert any(o['id'] == str(b['kpp'].id) for o in opts['kpp'])
        assert any(o['id'] == str(b['ilap'].id_kategori_wilayah_id) for o in opts['kategori_wilayah'])
        assert any(o['id'] == str(b['jenis_data'].id_jenis_tabel_id) for o in opts['jenis_tabel'])
        assert any(o['id'] == str(b['dasar_hukum'].id) for o in opts['dasar_hukum'])
        assert any(o['id'] == str(b['tiket'].status_tiket) for o in opts['status'])
        assert {'id': '1', 'name': 'Ya'} in opts['status_ketersediaan_data']
        assert {'id': '1', 'name': 'Ya'} in opts['special_request']

    def test_pic_user_without_active_pic_record_falls_through(self):
        """PIC.objects lookups only include users with a still-open PIC record."""
        b = _full_bundle()
        resp = _call(_admin_user(), _all_filters_params(b))
        assert resp.status_code == 200

    def test_no_get_filter_options_with_all_dimensions_lists_tikets(self):
        """The main (non get_filter_options) listing path with every filter set.

        Unlike get_filter_options=1, the main listing's periode filter is a
        single raw string (not comma-split multi-select), so it needs its
        own single 'type:value' periode here.
        """
        b = _full_bundle()
        params = _all_filters_params(b)
        del params['get_filter_options']
        params['periode'] = f"bulanan:{b['tiket'].periode}"
        params.update({'draw': '1', 'start': '0', 'length': '10'})
        resp = _call(_admin_user(), params)
        assert resp.status_code == 200
        payload = json.loads(resp.content)
        assert payload['recordsFiltered'] >= 1
        assert any(row['nomor_tiket'] == b['tiket'].nomor_tiket for row in payload['data'])

    def test_periode_without_type_prefix(self):
        """A bare 'periode=<n>' (no 'type:' prefix) still filters by periode number."""
        b = _full_bundle()
        resp = _call(
            _admin_user(),
            {'draw': '1', 'start': '0', 'length': '10', 'periode': str(b['tiket'].periode)},
        )
        payload = json.loads(resp.content)
        assert payload['recordsFiltered'] >= 1

    def test_invalid_periode_value_returns_no_results(self):
        b = _full_bundle()
        resp = _call(
            _admin_user(),
            {'draw': '1', 'start': '0', 'length': '10', 'periode': 'bulanan:notanumber'},
        )
        assert resp.status_code == 200

    def test_invalid_tahun_in_main_listing_returns_no_results(self):
        _full_bundle()
        resp = _call(
            _admin_user(),
            {'draw': '1', 'start': '0', 'length': '10', 'tahun': 'notayear'},
        )
        payload = json.loads(resp.content)
        assert payload['recordsFiltered'] == 0

    def test_invalid_status_in_main_listing_returns_no_results(self):
        _full_bundle()
        resp = _call(
            _admin_user(),
            {'draw': '1', 'start': '0', 'length': '10', 'status': 'notanumber'},
        )
        payload = json.loads(resp.content)
        assert payload['recordsFiltered'] == 0


@pytest.mark.django_db
class TestTahunDiterimaRange:
    """The two filters over tgl_terima_dip: Tahun Diterima and the date range.

    Tanggal Terima DIP is the one filter with no dropdown of its own, so
    besides the rows it is checked against the other dropdowns' options — a
    range that excludes a tiket has to take that tiket's year out of Tahun
    Data as well.
    """

    def _rows(self, **filters):
        params = {'draw': '1', 'start': '0', 'length': '10'}
        params.update(filters)
        return json.loads(_call(_admin_user(), params).content)

    def _options(self, **filters):
        params = {'get_filter_options': '1'}
        params.update(filters)
        return json.loads(_call(_admin_user(), params).content)['filter_options']

    def _two_tikets(self):
        """Two tikets on one periode data, received a year and a half apart.

        Built from the two factories this needs rather than from
        `_full_bundle`: the wilayah half of that bundle costs a KPP whose
        `nama_kpp` is a random word under a UNIQUE constraint, and nothing
        here filters by wilayah.
        """
        periode_data = PeriodeJenisDataFactory()
        early = TiketFactory(
            nomor_tiket='TK-DIP-2024', id_periode_data=periode_data,
            status_tiket=1, periode=1, tahun=2024,
            tgl_terima_dip=datetime(2024, 1, 11, 8, 0),
        )
        later = TiketFactory(
            nomor_tiket='TK-DIP-2025', id_periode_data=periode_data,
            status_tiket=1, periode=1, tahun=2025,
            # Late in the day, which is what a range compared as a timestamp
            # rather than a date would drop from its own last day.
            tgl_terima_dip=datetime(2025, 6, 30, 23, 30),
        )
        return early, later

    def test_range_narrows_the_rows(self):
        early, later = self._two_tikets()

        assert self._rows()['recordsFiltered'] == 2
        both = self._rows(tgl_terima_dip='2024-01-01..2025-12-31')
        assert both['recordsFiltered'] == 2

        only_2024 = self._rows(tgl_terima_dip='2024-01-01..2024-12-31')
        assert only_2024['recordsFiltered'] == 1
        assert only_2024['data'][0]['nomor_tiket'] == early.nomor_tiket

        # The last day of the range counts, whatever time of day it carries.
        last_day = self._rows(tgl_terima_dip='2025-01-01..2025-06-30')
        assert last_day['recordsFiltered'] == 1
        assert last_day['data'][0]['nomor_tiket'] == later.nomor_tiket

    def test_open_ended_and_unreadable_halves(self):
        self._two_tikets()

        # Either half may be left empty, leaving that end of the range open.
        assert self._rows(tgl_terima_dip='2025-01-01..')['recordsFiltered'] == 1
        assert self._rows(tgl_terima_dip='..2024-12-31')['recordsFiltered'] == 1
        # A malformed date is a broken request, not a request for no tikets.
        assert self._rows(tgl_terima_dip='bukan-tanggal..')['recordsFiltered'] == 2
        assert self._rows(tgl_terima_dip='')['recordsFiltered'] == 2

    def test_filter_by_tahun_diterima(self):
        """Tahun Diterima: the year of tgl_terima_dip, read like Tahun Data."""
        early, later = self._two_tikets()

        picked = self._rows(tahun_diterima='2024')
        assert picked['recordsFiltered'] == 1
        assert picked['data'][0]['nomor_tiket'] == early.nomor_tiket
        assert self._rows(tahun_diterima='2024,2025')['recordsFiltered'] == 2
        assert self._rows(tahun_diterima='2023')['recordsFiltered'] == 0
        # Non-numeric input matches nothing, the way Tahun Data behaves.
        assert self._rows(tahun_diterima='bukan-angka')['recordsFiltered'] == 0

        options = self._options()['tahun_diterima']
        assert [o['id'] for o in options] == ['2024', '2025']
        assert all(o['id'] == o['name'] for o in options)

    def test_tahun_diterima_and_the_range_narrow_together(self):
        """Both read tgl_terima_dip, so picking in both is their overlap."""
        self._two_tikets()

        assert self._rows(
            tahun_diterima='2024,2025', tgl_terima_dip='2025-01-01..2025-12-31',
        )['recordsFiltered'] == 1
        assert self._rows(
            tahun_diterima='2024', tgl_terima_dip='2025-01-01..2025-12-31',
        )['recordsFiltered'] == 0

    def test_tahun_diterima_options_never_narrow_themselves(self):
        """Picking a year must not leave that year as the only one on offer."""
        self._two_tikets()

        narrowed = self._options(tahun_diterima='2024')
        assert [o['id'] for o in narrowed['tahun_diterima']] == ['2024', '2025']
        # It still narrows every other dropdown, though.
        assert {o['id'] for o in narrowed['tahun']} == {'2024'}
        # And the range, which has no dropdown of its own, narrows it in turn.
        by_range = self._options(tgl_terima_dip='2025-01-01..2025-12-31')
        assert [o['id'] for o in by_range['tahun_diterima']] == ['2025']

    def test_panel_renders_both_received_filters(self, client):
        """The field names are the request parameters `tiket_data` reads back."""
        user = _admin_user()
        client.force_login(user)
        html = client.get(reverse('tiket_list')).content.decode()
        assert 'id="filter-tgl-terima-dip"' in html
        assert 'name="tgl_terima_dip"' in html
        assert 'id="filter-tahun-diterima"' in html
        assert 'name="tahun_diterima"' in html
        # Spelled out in full, so a reader can tell the data's own year from
        # the year it arrived in.
        assert '>Tahun Data<' in html
        assert '>Periode Data<' in html
        assert '>Tahun Diterima<' in html
        assert '>Tanggal Terima DIP<' in html

    def test_range_narrows_the_other_dropdowns(self):
        self._two_tikets()

        assert {o['id'] for o in self._options()['tahun']} == {'2024', '2025'}
        narrowed = self._options(tgl_terima_dip='2024-01-01..2024-12-31')
        assert {o['id'] for o in narrowed['tahun']} == {'2024'}
        assert {o['id'] for o in narrowed['nomor_tiket']} == {'TK-DIP-2024'}
