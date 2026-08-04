"""Tests for views/quality_control.py (view + data endpoint)."""
from datetime import date, datetime, timedelta
from itertools import count

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.constants.tiket_status import STATUS_PENGENDALIAN_MUTU
from diamond_web.models import DasarHukum, KlasifikasiJenisData, TiketPIC
from diamond_web.tests.conftest import (
    DurasiJatuhTempoFactory,
    JenisDataILAPFactory,
    JenisPrioritasDataFactory,
    JenisTabelFactory,
    PeriodeJenisDataFactory,
    PeriodePengirimanFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)
from diamond_web.views.quality_control import FILTER_APPLIERS, FILTER_OPTIONS


def _pmde_admin_user():
    return UserFactory(is_superuser=True)


def _kasi_pmde_user():
    """A supervisor, who sees every tiket in QC rather than only their own."""
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='kasi_pmde')
    user.groups.add(group)
    return user


_UNSET = object()
_PENYAMPAIAN_SEQ = count()


def _qc_bundle(with_durasi=True, with_prioritas=False, tgl_transfer=None,
               pmde_user=None, periode_penerimaan=None, tgl_rematch=_UNSET,
               durasi=10):
    jenis_tabel = JenisTabelFactory()
    jenis_data = JenisDataILAPFactory(id_jenis_tabel=jenis_tabel)
    # periode_penyampaian is unique and the factory draws it from a small word
    # list, so bundles created side by side collide unless it is spelled out.
    pengiriman_kwargs = {'periode_penyampaian': f'QC {next(_PENYAMPAIAN_SEQ)}'}
    if periode_penerimaan is not None:
        pengiriman_kwargs['periode_penerimaan'] = periode_penerimaan
    periode_data = PeriodeJenisDataFactory(
        id_sub_jenis_data_ilap=jenis_data,
        id_periode_pengiriman=PeriodePengirimanFactory(**pengiriman_kwargs),
    )
    tgl_transfer = tgl_transfer or datetime.now() - timedelta(days=5)
    # Anchored to mid-morning: the deadline counts from tgl_rematch, so a run
    # late in the evening would otherwise push it onto the following day.
    tgl_transfer = tgl_transfer.replace(hour=9, minute=0, second=0, microsecond=0)
    if tgl_rematch is _UNSET:
        tgl_rematch = tgl_transfer + timedelta(hours=2)
    tiket = TiketFactory(
        id_periode_data=periode_data,
        status_tiket=STATUS_PENGENDALIAN_MUTU,
        tgl_transfer=tgl_transfer,
        tgl_rematch=tgl_rematch,
        baris_i=100,
        sudah_qc=40,
        belum_qc=60,
    )
    group, _ = Group.objects.get_or_create(name='user_pmde')
    if pmde_user is None:
        pmde_user = UserFactory()
    pmde_user.groups.add(group)
    TiketPICFactory(id_tiket=tiket, id_user=pmde_user, role=TiketPIC.Role.PMDE, active=True)

    if with_durasi:
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis_data,
            seksi=group,
            durasi=durasi,
            start_date=date(2000, 1, 1),
            end_date=None,
        )

    if with_prioritas:
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=jenis_data,
            start_date=(tiket.tgl_terima_dip - timedelta(days=30)).date(),
            end_date=(tiket.tgl_terima_dip + timedelta(days=30)).date(),
        )

    # deskripsi is unique, so bundles created side by side need distinct ones.
    dasar_hukum = DasarHukum.objects.create(deskripsi=f'DH QC {tiket.pk}', kategori='PKS')
    KlasifikasiJenisData.objects.create(id_sub_jenis_data=jenis_data, id_klasifikasi_tabel=dasar_hukum)

    return {
        'tiket': tiket,
        'jenis_data': jenis_data,
        'jenis_tabel': jenis_tabel,
        'pmde_user': pmde_user,
        'group': group,
        'dasar_hukum': dasar_hukum,
    }


@pytest.mark.django_db
class TestQualityControlView:
    def test_get_denied_for_non_pmde(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse('quality_control'))
        assert resp.status_code == 403

    def test_get_success(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse('quality_control'))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestQualityControlData:
    url = 'quality_control_data'

    def test_data_endpoint_basic_row(self, client):
        bundle = _qc_bundle(with_durasi=True, with_prioritas=True)
        client.force_login(bundle['pmde_user'])
        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['recordsFiltered'] >= 1
        row = next(r for r in payload['data'] if r['nomor_tiket'] == bundle['tiket'].nomor_tiket)
        assert row['prioritas'] == 'Ya'
        assert row['jml_baris_i'] == 100
        assert row['jml_selesai'] == 40
        assert row['jml_progress'] == 60
        assert row['deadline']['display'] != '-'
        assert row['sisa_hari'] is not None

    def test_data_endpoint_no_durasi_no_prioritas(self, client):
        bundle = _qc_bundle(with_durasi=False, with_prioritas=False)
        client.force_login(bundle['pmde_user'])
        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        payload = resp.json()
        row = next(r for r in payload['data'] if r['nomor_tiket'] == bundle['tiket'].nomor_tiket)
        assert row['prioritas'] == 'Tidak'
        assert row['deadline']['display'] == '-'
        assert row['sisa_hari'] is None

    def test_deadline_does_not_bleed_between_rows(self, client):
        """A tiket with no durasi must not inherit the previous row's deadline."""
        with_durasi = _qc_bundle(with_durasi=True)
        without_durasi = _qc_bundle(with_durasi=False, pmde_user=with_durasi['pmde_user'])
        client.force_login(with_durasi['pmde_user'])

        # Ascending id, so the row that *has* a deadline is rendered first.
        resp = client.get(reverse(self.url), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '1', 'order[0][dir]': 'asc',
        })
        rows = {row['nomor_tiket']: row for row in resp.json()['data']}

        assert rows[with_durasi['tiket'].nomor_tiket]['sisa_hari'] is not None
        blank = rows[without_durasi['tiket'].nomor_tiket]
        assert blank['sisa_hari'] is None
        assert blank['deadline'] == {'display': '-', 'sort': ''}
        assert blank['jatuh_tempo'] == {'display': '-', 'sort': ''}

    def test_deadline_counts_from_tgl_rematch_when_it_is_set(self, client):
        """A rematched tiket starts its count again from tgl_rematch."""
        transfer = datetime.now() - timedelta(days=30)
        rematch = datetime.now() - timedelta(days=4)
        bundle = _qc_bundle(tgl_transfer=transfer, tgl_rematch=rematch)
        client.force_login(bundle['pmde_user'])

        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        row = next(r for r in resp.json()['data']
                   if r['nomor_tiket'] == bundle['tiket'].nomor_tiket)

        expected = (rematch + timedelta(days=10)).date()
        assert row['deadline']['display'] == expected.strftime('%d/%m/%Y')
        assert row['sisa_hari'] == (expected - date.today()).days

    def test_deadline_falls_back_to_tgl_transfer_without_a_rematch(self, client):
        bundle = _qc_bundle(tgl_transfer=datetime.now() - timedelta(days=30),
                            tgl_rematch=None)
        client.force_login(bundle['pmde_user'])

        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        row = next(r for r in resp.json()['data']
                   if r['nomor_tiket'] == bundle['tiket'].nomor_tiket)

        expected = (bundle['tiket'].tgl_transfer + timedelta(days=10)).date()
        assert row['deadline']['display'] == expected.strftime('%d/%m/%Y')

    def test_durasi_is_the_one_active_at_the_rematch_date(self, client):
        """The durasi row is picked by tgl_rematch, not by the older transfer."""
        transfer = datetime.now() - timedelta(days=60)
        rematch = datetime.now() - timedelta(days=3)
        bundle = _qc_bundle(tgl_transfer=transfer, tgl_rematch=rematch, with_durasi=False)
        # Closed before the rematch: it covers tgl_transfer only, so it must lose.
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=bundle['jenis_data'],
            seksi=bundle['group'],
            durasi=99,
            start_date=date(2000, 1, 1),
            end_date=(transfer + timedelta(days=1)).date(),
        )
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=bundle['jenis_data'],
            seksi=bundle['group'],
            durasi=7,
            start_date=(transfer + timedelta(days=2)).date(),
            end_date=None,
        )
        client.force_login(bundle['pmde_user'])

        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        row = next(r for r in resp.json()['data']
                   if r['nomor_tiket'] == bundle['tiket'].nomor_tiket)

        expected = (rematch + timedelta(days=7)).date()
        assert row['deadline']['display'] == expected.strftime('%d/%m/%Y')

    def test_deadline_sorting_follows_the_rematch_date(self, client):
        """The SQL used for sorting counts from the same date the display does."""
        # Transferred earlier but rematched later, so the two orders disagree.
        early = _qc_bundle(tgl_transfer=datetime.now() - timedelta(days=40),
                           tgl_rematch=datetime.now() - timedelta(days=2))
        late = _qc_bundle(tgl_transfer=datetime.now() - timedelta(days=20),
                          tgl_rematch=datetime.now() - timedelta(days=10),
                          pmde_user=early['pmde_user'])
        client.force_login(early['pmde_user'])

        resp = client.get(reverse(self.url), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '8', 'order[0][dir]': 'asc',
        })
        nomor = [row['nomor_tiket'] for row in resp.json()['data']]
        assert nomor == [late['tiket'].nomor_tiket, early['tiket'].nomor_tiket]

    def test_data_endpoint_post_method(self, client):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        resp = client.post(reverse(self.url), {'draw': '2', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 2

    def test_data_endpoint_only_shows_own_pmde_tikets(self, client):
        _qc_bundle()
        other_pmde = UserFactory()
        group, _ = Group.objects.get_or_create(name='user_pmde')
        other_pmde.groups.add(group)
        client.force_login(other_pmde)
        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.json()['recordsFiltered'] == 0

    @pytest.mark.parametrize('order_col,order_dir', [
        (0, 'asc'), (1, 'desc'), (9, 'asc'), (10, 'desc'), (11, 'asc'), (99, 'asc'),
    ])
    def test_ordering(self, client, order_col, order_dir):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10',
             'order[0][column]': str(order_col), 'order[0][dir]': order_dir},
        )
        assert resp.status_code == 200

    def test_ordering_invalid_column_falls_back(self, client):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'abc'},
        )
        assert resp.status_code == 200

    def test_denied_for_non_pmde(self, client):
        """@user_passes_test redirects (not 403) non-PMDE users."""
        client.force_login(UserFactory())
        resp = client.get(reverse(self.url))
        assert resp.status_code == 302


@pytest.mark.django_db
class TestQualityControlFilters:
    """The filter panel shared in shape with the tiket list page."""

    url = 'quality_control_data'

    def _rows(self, client, **filters):
        params = {'draw': '1', 'start': '0', 'length': '10'}
        params.update(filters)
        resp = client.get(reverse(self.url), params)
        assert resp.status_code == 200
        return resp.json()

    def _options(self, client, **filters):
        params = {'get_filter_options': '1'}
        params.update(filters)
        resp = client.get(reverse(self.url), params)
        assert resp.status_code == 200
        return resp.json()['filter_options']

    def test_filter_options_cover_every_dropdown(self, client):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        options = self._options(client)
        # Each filter the backend accepts must also offer options, otherwise
        # the panel would render a dropdown nothing can ever be picked from.
        assert set(options) == set(FILTER_APPLIERS) == set(FILTER_OPTIONS)

    def test_filter_options_reflect_the_scoped_tikets(self, client):
        bundle = _qc_bundle(with_prioritas=True)
        client.force_login(bundle['pmde_user'])
        options = self._options(client)

        assert [o['id'] for o in options['nomor_tiket']] == [bundle['tiket'].nomor_tiket]
        assert [o['id'] for o in options['ilap']] == [str(bundle['jenis_data'].id_ilap.id)]
        assert [o['id'] for o in options['jenis_tabel']] == [str(bundle['jenis_tabel'].id)]
        assert [o['id'] for o in options['prioritas']] == ['1']

    def test_filter_options_narrow_each_other(self, client):
        first = _qc_bundle()
        second = _qc_bundle(pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        assert len(self._options(client)['ilap']) == 2

        narrowed = self._options(client, nomor_tiket=second['tiket'].nomor_tiket)
        assert [o['id'] for o in narrowed['ilap']] == [str(second['jenis_data'].id_ilap.id)]
        # A dropdown never narrows itself, or its own selection would vanish.
        assert len(narrowed['nomor_tiket']) == 2

    def test_filter_by_nomor_tiket(self, client):
        first = _qc_bundle()
        second = _qc_bundle(pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        payload = self._rows(client, nomor_tiket=first['tiket'].nomor_tiket)
        assert payload['recordsTotal'] == 2
        assert payload['recordsFiltered'] == 1
        assert payload['data'][0]['nomor_tiket'] == first['tiket'].nomor_tiket

    def test_filter_accepts_multiple_values(self, client):
        first = _qc_bundle()
        second = _qc_bundle(pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        payload = self._rows(
            client,
            nomor_tiket=f"{first['tiket'].nomor_tiket},{second['tiket'].nomor_tiket}",
        )
        assert payload['recordsFiltered'] == 2

    @pytest.mark.parametrize('with_prioritas,selected,expected', [
        (True, '1', 1),
        (True, '0', 0),
        (False, '0', 1),
        (False, '1', 0),
    ])
    def test_filter_prioritas(self, client, with_prioritas, selected, expected):
        bundle = _qc_bundle(with_prioritas=with_prioritas)
        client.force_login(bundle['pmde_user'])
        assert self._rows(client, prioritas=selected)['recordsFiltered'] == expected

    def test_filter_prioritas_both_values_matches_everything(self, client):
        first = _qc_bundle(with_prioritas=True)
        _qc_bundle(with_prioritas=False, pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])
        assert self._rows(client, prioritas='1,0')['recordsFiltered'] == 2

    def test_filter_by_ilap_and_sub_jenis_data(self, client):
        first = _qc_bundle()
        second = _qc_bundle(pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        assert self._rows(client, ilap=str(first['jenis_data'].id_ilap.id))['recordsFiltered'] == 1
        assert self._rows(
            client, sub_jenis_data=second['jenis_data'].id_sub_jenis_data
        )['recordsFiltered'] == 1

    def test_filter_by_jenis_tabel_and_dasar_hukum(self, client):
        first = _qc_bundle()
        _qc_bundle(pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        assert self._rows(client, jenis_tabel=str(first['jenis_tabel'].id))['recordsFiltered'] == 1
        assert self._rows(
            client, dasar_hukum=str(first['dasar_hukum'].id)
        )['recordsFiltered'] == 1

    def test_filter_by_pic_pmde(self, client):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        assert self._rows(client, pic_pmde=str(bundle['pmde_user'].id))['recordsFiltered'] == 1
        assert self._rows(client, pic_pmde=str(UserFactory().id))['recordsFiltered'] == 0

    def test_filter_by_tahun(self, client):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        tahun = bundle['tiket'].tahun
        assert self._rows(client, tahun=str(tahun))['recordsFiltered'] == 1
        assert self._rows(client, tahun=str(tahun + 1))['recordsFiltered'] == 0

    def test_filter_tahun_ignores_non_numeric_input(self, client):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        assert self._rows(client, tahun='bukan-angka')['recordsFiltered'] == 0

    def test_filter_by_periode_with_type_prefix(self, client):
        bundle = _qc_bundle(periode_penerimaan='Bulanan')
        client.force_login(bundle['pmde_user'])
        periode = bundle['tiket'].periode
        assert self._rows(client, periode=f'bulanan:{periode}')['recordsFiltered'] == 1
        # Same number, wrong periode type — a monthly tiket is not a quarterly one.
        assert self._rows(client, periode=f'triwulanan:{periode}')['recordsFiltered'] == 0

    def test_filter_by_status_ketersediaan_data(self, client):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        available = '1' if bundle['tiket'].status_ketersediaan_data else '0'
        assert self._rows(client, status_ketersediaan_data=available)['recordsFiltered'] == 1

    def test_filters_combine(self, client):
        first = _qc_bundle(with_prioritas=True)
        second = _qc_bundle(pmde_user=first['pmde_user'], with_prioritas=False)
        client.force_login(first['pmde_user'])

        payload = self._rows(
            client,
            nomor_tiket=f"{first['tiket'].nomor_tiket},{second['tiket'].nomor_tiket}",
            prioritas='1',
        )
        assert payload['recordsFiltered'] == 1
        assert payload['data'][0]['nomor_tiket'] == first['tiket'].nomor_tiket

    def test_filters_apply_to_post_requests_too(self, client):
        first = _qc_bundle()
        _qc_bundle(pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        resp = client.post(reverse(self.url), {
            'draw': '1', 'start': '0', 'length': '10',
            'nomor_tiket': first['tiket'].nomor_tiket,
        })
        assert resp.json()['recordsFiltered'] == 1


@pytest.mark.django_db
class TestQualityControlChart:
    """The progress chart: Jml Progress per jatuh tempo, one line per PIC PMDE."""

    url = 'quality_control_data'

    def _chart(self, client, **filters):
        params = {'get_chart_data': '1'}
        params.update(filters)
        resp = client.get(reverse(self.url), params)
        assert resp.status_code == 200
        return resp.json()

    def test_series_are_grouped_per_pic_pmde(self, client):
        kasi = _kasi_pmde_user()
        first = _qc_bundle()
        second = _qc_bundle()
        client.force_login(kasi)

        payload = self._chart(client)
        names = {s['name'] for s in payload['series']}
        assert names == {
            first['pmde_user'].get_full_name() or first['pmde_user'].username,
            second['pmde_user'].get_full_name() or second['pmde_user'].username,
        }
        # Both bundles transfer on the same day with the same durasi, so they
        # land on one jatuh tempo carrying each PIC's own Jml Progress.
        assert len(payload['categories']) == 1
        assert [s['data'] for s in payload['series']] == [[60], [60]]

    def test_progress_of_the_same_pic_is_summed_per_jatuh_tempo(self, client):
        first = _qc_bundle()
        _qc_bundle(pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        payload = self._chart(client)
        assert len(payload['series']) == 1
        assert payload['series'][0]['data'] == [120]

    def test_categories_are_the_jatuh_tempo_in_ascending_order(self, client):
        recent = _qc_bundle(tgl_transfer=datetime.now() - timedelta(days=5))
        older = _qc_bundle(
            pmde_user=recent['pmde_user'],
            tgl_transfer=datetime.now() - timedelta(days=40),
        )
        client.force_login(recent['pmde_user'])

        payload = self._chart(client)
        # durasi is 10 days, so 40 days ago is well past due and 5 days ago
        # still has time left — the overdue one sorts first.
        assert payload['categories'] == ['-30 hari', '5 hari']
        assert payload['series'][0]['data'] == [60, 60]
        assert older['tiket'].pk != recent['tiket'].pk

    def test_tiket_without_a_deadline_is_left_out(self, client):
        bundle = _qc_bundle(with_durasi=False)
        client.force_login(bundle['pmde_user'])

        payload = self._chart(client)
        assert payload == {'categories': [], 'series': []}

    def test_tiket_without_an_active_pic_pmde_gets_its_own_series(self, client):
        bundle = _qc_bundle()
        TiketPIC.objects.filter(id_tiket=bundle['tiket']).update(active=False)
        client.force_login(_kasi_pmde_user())

        payload = self._chart(client)
        assert [s['name'] for s in payload['series']] == ['Tanpa PIC PMDE']

    def test_colours_survive_a_filter(self, client):
        """A PIC keeps its colour when a filter drops the other PIC's tikets."""
        kasi = _kasi_pmde_user()
        first = _qc_bundle()
        second = _qc_bundle()
        client.force_login(kasi)

        unfiltered = {s['name']: s['color'] for s in self._chart(client)['series']}
        assert len(set(unfiltered.values())) == 2

        for bundle in (first, second):
            narrowed = self._chart(client, nomor_tiket=bundle['tiket'].nomor_tiket)
            assert len(narrowed['series']) == 1
            series = narrowed['series'][0]
            assert series['color'] == unfiltered[series['name']]

    def test_filters_narrow_the_chart(self, client):
        first = _qc_bundle()
        _qc_bundle(pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        payload = self._chart(client, nomor_tiket=first['tiket'].nomor_tiket)
        assert payload['series'][0]['data'] == [60]

    def test_ninth_pic_repeats_a_colour_with_a_dashed_line(self, client):
        """Past the eighth PIC identity rests on the dash, not on a new hue."""
        kasi = _kasi_pmde_user()
        bundles = [_qc_bundle() for _ in range(9)]
        client.force_login(kasi)

        series = self._chart(client)['series']
        assert len(series) == 9
        assert [s['dashed'] for s in series] == [False] * 8 + [True]
        assert series[8]['color'] == series[0]['color']
        assert len({s['color'] for s in series[:8]}) == 8
        assert len(bundles) == 9

    def test_denied_for_non_pmde(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse(self.url), {'get_chart_data': '1'})
        assert resp.status_code == 302
