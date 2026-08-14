"""Tests for views/quality_control.py (view + data endpoint)."""
from datetime import date, datetime, timedelta
from itertools import count

import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone

from diamond_web.constants.tiket_action_types import TiketActionType
from diamond_web.constants.tiket_status import (
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_DIREKAM,
    STATUS_DITELITI,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
    STATUSES_DI_P3DE,
    STATUSES_DI_PIDE,
)
from diamond_web.models import DasarHukum, JenisTabel, KlasifikasiJenisData, TiketPIC
from diamond_web.models.kategori_wilayah import KategoriWilayah
from diamond_web.models.tiket_action import TiketAction
from diamond_web.tests.conftest import (
    DurasiJatuhTempoFactory,
    ILAPFactory,
    JenisDataILAPFactory,
    JenisPrioritasDataFactory,
    JenisTabelFactory,
    PeriodeJenisDataFactory,
    PeriodePengirimanFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)
from diamond_web.views.quality_control import (
    FILTER_APPLIERS,
    FILTER_OPTIONS,
    JENIS_TABEL_WEIGHTS,
    KATEGORI_WILAYAH_WEIGHTS,
    PRIORITAS_WEIGHT,
)


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
               durasi=10, jenis_tabel=None, belum_qc=60, kategori_wilayah=None):
    jenis_tabel = jenis_tabel or JenisTabelFactory()
    ilap_kwargs = {}
    if kategori_wilayah is not None:
        ilap_kwargs['id_ilap'] = ILAPFactory(id_kategori_wilayah=kategori_wilayah)
    jenis_data = JenisDataILAPFactory(id_jenis_tabel=jenis_tabel, **ilap_kwargs)
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
        belum_qc=belum_qc,
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


def _jatuh_tempo_bundle(days, **kwargs):
    """A bundle whose jatuh tempo is `days` days from today, negative allowed.

    The deadline counts the durasi from tgl_transfer, which `_qc_bundle` puts
    five days back, so the durasi that lands the deadline on the wanted day is
    that gap plus those five days.
    """
    return _qc_bundle(durasi=days + 5, **kwargs)


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

    def test_page_names_the_payload_keys_the_endpoint_sends(self, client):
        """The shared template reads its variable columns out of a config block.

        Nothing else ties the two halves together, so a key renamed on one side
        would silently blank a column; this is what notices.
        """
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        html = client.get(reverse('quality_control')).content.decode()
        row = client.get(
            reverse('quality_control_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        ).json()['data'][0]

        for key in ('pic_pmde', 'tgl_transfer', 'tgl_rematch',
                    'jml_baris_i', 'jml_selesai', 'jml_progress'):
            assert f"'{key}'" in html
            assert key in row


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
            'order[0][column]': '5', 'order[0][dir]': 'asc',
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

    def test_filter_by_nama_tabel(self, client):
        """Nama tabel is free text, so the option id is the name itself."""
        first = _qc_bundle()
        second = _qc_bundle(pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        options = self._options(client)
        assert {o['id'] for o in options['nama_tabel']} == {
            first['jenis_data'].nama_tabel_I, second['jenis_data'].nama_tabel_I
        }
        assert all(o['id'] == o['name'] for o in options['nama_tabel'])

        payload = self._rows(client, nama_tabel=first['jenis_data'].nama_tabel_I)
        assert payload['recordsFiltered'] == 1
        assert payload['data'][0]['nama_tabel'] == first['jenis_data'].nama_tabel_I

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
        # Same number, wrong periode type â€” a monthly tiket is not a quarterly one.
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

    def test_filter_jatuh_tempo_thresholds(self, client):
        near = _jatuh_tempo_bundle(5)
        _jatuh_tempo_bundle(20, pmde_user=near['pmde_user'])
        _jatuh_tempo_bundle(50, pmde_user=near['pmde_user'])
        client.force_login(near['pmde_user'])

        assert self._rows(client)['recordsFiltered'] == 3           # -- Semua --
        assert self._rows(client, jatuh_tempo='10')['recordsFiltered'] == 1
        assert self._rows(client, jatuh_tempo='30')['recordsFiltered'] == 2
        assert self._rows(client, jatuh_tempo='60')['recordsFiltered'] == 3

        under_ten = self._rows(client, jatuh_tempo='10')['data']
        assert [row['nomor_tiket'] for row in under_ten] == [near['tiket'].nomor_tiket]
        assert under_ten[0]['jatuh_tempo']['display'] == '5 hari'

    def test_filter_jatuh_tempo_takes_the_widest_threshold(self, client):
        first = _jatuh_tempo_bundle(5)
        _jatuh_tempo_bundle(50, pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        # The thresholds nest, so picking several is the union of them.
        assert self._rows(client, jatuh_tempo='10,60')['recordsFiltered'] == 2

    def test_filter_jatuh_tempo_includes_an_overdue_tiket(self, client):
        bundle = _jatuh_tempo_bundle(-3)
        client.force_login(bundle['pmde_user'])
        # Its jatuh tempo is negative, which is under every threshold.
        assert self._rows(client, jatuh_tempo='10')['recordsFiltered'] == 1

    def test_filter_jatuh_tempo_excludes_a_tiket_without_a_deadline(self, client):
        bundle = _qc_bundle(with_durasi=False)
        client.force_login(bundle['pmde_user'])

        assert self._rows(client)['recordsFiltered'] == 1
        assert self._rows(client, jatuh_tempo='60')['recordsFiltered'] == 0

    @pytest.mark.parametrize('selected', ['bukan-angka', '15'])
    def test_filter_jatuh_tempo_rejects_a_value_it_does_not_offer(self, client, selected):
        bundle = _jatuh_tempo_bundle(5)
        client.force_login(bundle['pmde_user'])
        assert self._rows(client, jatuh_tempo=selected)['recordsFiltered'] == 0

    def test_jatuh_tempo_options_are_the_fixed_thresholds(self, client):
        bundle = _jatuh_tempo_bundle(5)
        client.force_login(bundle['pmde_user'])

        # Offered whether or not anything currently falls in them, unlike every
        # other dropdown, which is read off the result set.
        options = self._options(client)['jatuh_tempo']
        assert [o['id'] for o in options] == ['10', '30', '60']
        assert [o['name'] for o in options] == ['< 10 hari', '< 30 hari', '< 60 hari']
        assert self._options(client, jatuh_tempo='10')['jatuh_tempo'] == options

    def test_jatuh_tempo_narrows_the_other_dropdowns(self, client):
        near = _jatuh_tempo_bundle(5)
        far = _jatuh_tempo_bundle(50, pmde_user=near['pmde_user'])
        client.force_login(near['pmde_user'])

        assert len(self._options(client)['nomor_tiket']) == 2
        narrowed = self._options(client, jatuh_tempo='10')
        assert [o['id'] for o in narrowed['nomor_tiket']] == [near['tiket'].nomor_tiket]
        assert far['tiket'].nomor_tiket not in [o['id'] for o in narrowed['nomor_tiket']]

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
        # still has time left â€” the overdue one sorts first.
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


def _upstream_bundle(status_tiket, pmde_user=None, jenis_tabel=None, **baris):
    """A tiket still at P3DE or PIDE, with a PMDE PIC already assigned.

    PMDE PICs are attached when a tiket is recorded rather than when it is
    transferred, which is what puts an upstream tiket inside a pelaksana's scope
    on this page even though it has not reached quality control yet.
    """
    jenis_data_kwargs = {}
    if jenis_tabel is not None:
        jenis_data_kwargs['id_jenis_tabel'] = jenis_tabel
    periode_data = PeriodeJenisDataFactory(
        id_sub_jenis_data_ilap=JenisDataILAPFactory(**jenis_data_kwargs),
        id_periode_pengiriman=PeriodePengirimanFactory(
            periode_penyampaian=f'QC {next(_PENYAMPAIAN_SEQ)}',
        ),
    )
    tiket = TiketFactory(
        id_periode_data=periode_data, status_tiket=status_tiket, **baris,
    )
    group, _ = Group.objects.get_or_create(name='user_pmde')
    if pmde_user is None:
        pmde_user = UserFactory()
    pmde_user.groups.add(group)
    TiketPICFactory(id_tiket=tiket, id_user=pmde_user, role=TiketPIC.Role.PMDE, active=True)
    return {'tiket': tiket, 'pmde_user': pmde_user}


def _selesai_bundle(days_ago=5, pmde_user=None, jenis_tabel=None, sudah_qc=250,
                    action=TiketActionType.SELESAI, status=STATUS_SELESAI):
    """A tiket closed `days_ago` days ago, with a PMDE PIC on it.

    Completion is the SELESAI action rather than a column on the tiket, so the
    bundle writes one — which is what the 90 day window is read from.
    """
    bundle = _upstream_bundle(
        status, pmde_user=pmde_user, jenis_tabel=jenis_tabel, sudah_qc=sudah_qc,
    )
    TiketAction.objects.create(
        id_tiket=bundle['tiket'],
        id_user=bundle['pmde_user'],
        timestamp=timezone.now() - timedelta(days=days_ago),
        action=action,
    )
    return bundle


def _seeded_kinds():
    """The three jenis tabel the reference table is seeded with by migration."""
    return [
        JenisTabel.objects.get(deskripsi=deskripsi)
        for deskripsi in ('Diidentifikasi', 'Tidak Diidentifikasi', 'Tidak Terstruktur')
    ]


def _entries(section, split='jenis_tabel'):
    """One of a summary section's splits, keyed by entry name."""
    return {entry['name']: entry for entry in section['splits'][split]}


def _counts(entry):
    """An entry's counted figures, without the weighted load beside them.

    The load is asserted where it is the subject (see TestIndeksBeban); every
    other test is about the counting and says so by leaving it out.
    """
    return {key: entry[key] for key in ('name', 'tikets', 'baris')}


class SummaryEndpoint:
    """Shared access to the summary payload's sections."""

    url = 'quality_control_data'

    def _summary(self, client, **filters):
        params = {'get_summary': '1'}
        params.update(filters)
        resp = client.get(reverse(self.url), params)
        assert resp.status_code == 200
        return resp.json()

    def _section(self, client, key, **filters):
        return self._summary(client, **filters)[key]


@pytest.mark.django_db
class TestQualityControlSummary(SummaryEndpoint):
    """The three sections above the chart: the QC queue, then P3DE and PIDE."""

    def test_counts_tikets_and_sums_belum_qc(self, client):
        first = _qc_bundle()
        _qc_bundle(pmde_user=first['pmde_user'])
        client.force_login(first['pmde_user'])

        qc = self._section(client, 'qc')
        assert qc['tikets'] == 2
        # 60 belum_qc each, per _qc_bundle.
        assert qc['baris'] == 120

    def test_unset_belum_qc_counts_as_no_rows(self, client):
        """A tiket that has not been counted yet still counts as a tiket."""
        bundle = _qc_bundle(belum_qc=None)
        client.force_login(bundle['pmde_user'])

        qc = self._section(client, 'qc')
        assert qc['tikets'] == 1
        assert qc['baris'] == 0

    def test_qc_tiket_is_in_no_upstream_section(self, client):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])

        payload = self._summary(client)
        assert payload['qc']['tikets'] == 1
        for key in ('p3de', 'pide'):
            assert payload[key]['tikets'] == 0
            assert payload[key]['baris'] == 0

    def test_upstream_tiket_is_not_counted_as_qc(self, client):
        bundle = _upstream_bundle(STATUS_DIREKAM, baris_lengkap=500)
        client.force_login(bundle['pmde_user'])

        payload = self._summary(client)
        assert payload['qc']['tikets'] == 0
        assert payload['qc']['baris'] == 0
        assert payload['p3de']['tikets'] == 1

    @pytest.mark.parametrize('status', list(STATUSES_DI_P3DE))
    def test_a_p3de_tiket_lands_in_the_p3de_section_only(self, client, status):
        """Below Dikirim ke PIDE the P3DE count is the only one taken."""
        bundle = _upstream_bundle(status, baris_lengkap=500, baris_i=7)
        client.force_login(bundle['pmde_user'])

        payload = self._summary(client)
        assert (payload['p3de']['tikets'], payload['p3de']['baris']) == (1, 500)
        assert payload['pide']['tikets'] == 0

    @pytest.mark.parametrize('status', list(STATUSES_DI_PIDE))
    def test_a_pide_tiket_lands_in_the_pide_section_only(self, client, status):
        """From Dikirim ke PIDE on, baris I is the part still to be processed."""
        bundle = _upstream_bundle(
            status, baris_lengkap=500, baris_i=300, baris_u=100,
            baris_cde=60, baris_res=40,
        )
        client.force_login(bundle['pmde_user'])

        payload = self._summary(client)
        assert payload['pide']['tikets'] == 1
        assert payload['pide']['baris'] == 300
        assert payload['p3de']['tikets'] == 0

    @pytest.mark.parametrize('status', list(STATUSES_DI_PIDE))
    def test_at_pide_an_empty_split_falls_back_to_baris_lengkap(self, client, status):
        """Identification has recorded nothing yet, so baris lengkap still stands."""
        bundle = _upstream_bundle(
            status, baris_lengkap=500, baris_i=0, baris_u=0, baris_cde=0, baris_res=0,
        )
        client.force_login(bundle['pmde_user'])

        assert self._section(client, 'pide')['baris'] == 500

    @pytest.mark.parametrize('status', list(STATUSES_DI_PIDE))
    def test_at_pide_unset_baris_fall_back_to_baris_lengkap(self, client, status):
        """The legacy rows leave the split null rather than zero."""
        bundle = _upstream_bundle(status, baris_lengkap=500)
        client.force_login(bundle['pmde_user'])

        assert self._section(client, 'pide')['baris'] == 500

    def test_rows_of_several_tikets_in_a_section_are_summed(self, client):
        first = _upstream_bundle(STATUS_DIREKAM, baris_lengkap=500)
        _upstream_bundle(
            STATUS_DITELITI, pmde_user=first['pmde_user'], baris_lengkap=300,
        )
        _upstream_bundle(
            STATUS_IDENTIFIKASI, pmde_user=first['pmde_user'],
            baris_lengkap=900, baris_i=200, baris_u=700,
        )
        client.force_login(first['pmde_user'])

        payload = self._summary(client)
        assert payload['p3de']['tikets'] == 2
        assert payload['p3de']['baris'] == 800
        assert payload['pide']['tikets'] == 1
        assert payload['pide']['baris'] == 200

    def test_a_pelaksana_sees_only_their_own_scope(self, client):
        mine = _qc_bundle()
        _qc_bundle()
        _upstream_bundle(STATUS_DIREKAM, baris_lengkap=500)
        client.force_login(mine['pmde_user'])

        payload = self._summary(client)
        assert payload['qc']['tikets'] == 1
        assert payload['p3de']['tikets'] == 0

    def test_kasi_sees_the_whole_seksi(self, client):
        _qc_bundle()
        _qc_bundle()
        _upstream_bundle(STATUS_DIREKAM, baris_lengkap=500)
        _upstream_bundle(STATUS_IDENTIFIKASI, baris_lengkap=40)
        client.force_login(_kasi_pmde_user())

        payload = self._summary(client)
        assert payload['qc']['tikets'] == 2
        assert payload['p3de']['tikets'] == 1
        assert payload['pide']['tikets'] == 1

    def test_filters_narrow_every_section(self, client):
        qc_bundle = _qc_bundle()
        user = qc_bundle['pmde_user']
        p3de = _upstream_bundle(STATUS_DIREKAM, pmde_user=user, baris_lengkap=500)
        _upstream_bundle(STATUS_IDENTIFIKASI, pmde_user=user, baris_lengkap=40)
        client.force_login(user)

        payload = self._summary(client, nomor_tiket=p3de['tiket'].nomor_tiket)
        assert payload['qc']['tikets'] == 0
        assert payload['qc']['baris'] == 0
        assert payload['p3de']['tikets'] == 1
        assert payload['p3de']['baris'] == 500
        assert payload['pide']['tikets'] == 0

    def test_jatuh_tempo_filter_leaves_the_upstream_sections_alone(self, client):
        """Jatuh tempo counts from a transfer date an upstream tiket lacks.

        Applying it there would empty the upstream sections rather than narrow
        them, so the QC-only filter is dropped from those two.
        """
        qc_bundle = _jatuh_tempo_bundle(5)
        user = qc_bundle['pmde_user']
        _upstream_bundle(STATUS_DIREKAM, pmde_user=user, baris_lengkap=500)
        _upstream_bundle(STATUS_IDENTIFIKASI, pmde_user=user, baris_lengkap=40)
        client.force_login(user)

        payload = self._summary(client, jatuh_tempo='10')
        assert payload['qc']['tikets'] == 1
        assert payload['p3de']['tikets'] == 1
        assert payload['p3de']['baris'] == 500
        assert payload['pide']['tikets'] == 1
        assert payload['pide']['baris'] == 40

    def test_denied_for_non_pmde(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse(self.url), {'get_summary': '1'})
        assert resp.status_code == 302


@pytest.mark.django_db
class TestSummaryBreakdown(SummaryEndpoint):
    """Every section's split by jenis tabel — the detail lines under a PIC."""

    def test_every_section_carries_the_split(self, client):
        identified, unidentified, unstructured = _seeded_kinds()
        first = _upstream_bundle(
            STATUS_DIREKAM, jenis_tabel=identified, baris_lengkap=500,
        )
        user = first['pmde_user']
        _upstream_bundle(
            STATUS_DITELITI, pmde_user=user, jenis_tabel=identified, baris_lengkap=300,
        )
        _upstream_bundle(
            STATUS_DIREKAM, pmde_user=user, jenis_tabel=unidentified, baris_lengkap=900,
        )
        _upstream_bundle(
            STATUS_DIREKAM, pmde_user=user, jenis_tabel=unstructured, baris_lengkap=40,
        )
        client.force_login(user)

        payload = self._summary(client)
        entries = _entries(payload['p3de'])
        assert _counts(entries['Diidentifikasi']) == {
            'name': 'Diidentifikasi', 'tikets': 2, 'baris': 800,
        }
        assert entries['Tidak Diidentifikasi']['baris'] == 900
        assert entries['Tidak Terstruktur']['baris'] == 40
        # The split accounts for the headline exactly.
        assert payload['p3de']['tikets'] == 4
        assert payload['p3de']['baris'] == 1740
        # And every section is split every way, in the same order, so a detail
        # line can be read straight across.
        for key in ('qc', 'p3de', 'pide', 'selesai'):
            assert set(payload[key]['splits']) == {'jenis_tabel', 'kategori_wilayah'}
            for split in ('jenis_tabel', 'kategori_wilayah'):
                assert [entry['name'] for entry in payload[key]['splits'][split]] == [
                    entry['name'] for entry in payload['p3de']['splits'][split]
                ]

    def test_the_pide_breakdown_uses_the_identified_row_count(self, client):
        identified, unidentified, _unstructured = _seeded_kinds()
        first = _upstream_bundle(
            STATUS_IDENTIFIKASI, jenis_tabel=identified,
            baris_lengkap=900, baris_i=200, baris_u=700,
        )
        _upstream_bundle(
            STATUS_DIKIRIM_KE_PIDE, pmde_user=first['pmde_user'],
            jenis_tabel=unidentified, baris_lengkap=500,
        )
        client.force_login(first['pmde_user'])

        pide = self._section(client, 'pide')
        entries = _entries(pide)
        # Split recorded, so baris I; split still empty, so baris lengkap.
        assert entries['Diidentifikasi']['baris'] == 200
        assert entries['Tidak Diidentifikasi']['baris'] == 500
        assert pide['baris'] == 700

    def test_splits_qc_tikets_and_rows_per_jenis_tabel(self, client):
        identified, unidentified, _unstructured = _seeded_kinds()
        first = _qc_bundle(jenis_tabel=identified, belum_qc=60)
        _qc_bundle(pmde_user=first['pmde_user'], jenis_tabel=identified, belum_qc=25)
        _qc_bundle(pmde_user=first['pmde_user'], jenis_tabel=unidentified, belum_qc=10)
        client.force_login(first['pmde_user'])

        qc = self._section(client, 'qc')
        entries = _entries(qc)
        assert _counts(entries['Diidentifikasi']) == {
            'name': 'Diidentifikasi', 'tikets': 2, 'baris': 85,
        }
        assert _counts(entries['Tidak Diidentifikasi']) == {
            'name': 'Tidak Diidentifikasi', 'tikets': 1, 'baris': 10,
        }
        assert qc['tikets'] == 3
        assert qc['baris'] == 95

    def test_the_qc_section_lists_every_jenis_tabel_in_reference_order(self, client):
        """A kind with nothing pending keeps its column, showing a zero."""
        _identified, _unidentified, unstructured = _seeded_kinds()
        bundle = _qc_bundle(jenis_tabel=unstructured)
        client.force_login(bundle['pmde_user'])

        # The seeded kinds keep the order the reference table gives them. Extra
        # rows appear too: every factory-made tiket brings a jenis tabel of its
        # own, and a section lists whatever the reference table holds.
        seeded = ['Diidentifikasi', 'Tidak Diidentifikasi', 'Tidak Terstruktur']
        qc = self._section(client, 'qc')
        names = [entry['name'] for entry in qc['splits']['jenis_tabel']]
        assert [name for name in names if name in seeded] == seeded
        assert _counts(_entries(qc)['Diidentifikasi']) == {
            'name': 'Diidentifikasi', 'tikets': 0, 'baris': 0,
        }

    def test_each_section_only_counts_its_own_queue(self, client):
        identified, _unidentified, _unstructured = _seeded_kinds()
        qc_bundle = _qc_bundle(jenis_tabel=identified)
        user = qc_bundle['pmde_user']
        _upstream_bundle(
            STATUS_DIREKAM, pmde_user=user, jenis_tabel=identified, baris_lengkap=500,
        )
        _upstream_bundle(
            STATUS_DIKIRIM_KE_PIDE, pmde_user=user, jenis_tabel=identified,
            baris_lengkap=40,
        )
        client.force_login(user)

        payload = self._summary(client)
        assert _counts(_entries(payload['qc'])['Diidentifikasi']) == {
            'name': 'Diidentifikasi', 'tikets': 1, 'baris': 60,
        }
        assert (payload['p3de']['tikets'], payload['p3de']['baris']) == (1, 500)
        assert (payload['pide']['tikets'], payload['pide']['baris']) == (1, 40)

    def test_filters_narrow_the_breakdown(self, client):
        identified, unidentified, _unstructured = _seeded_kinds()
        first = _qc_bundle(jenis_tabel=identified, belum_qc=500)
        _qc_bundle(
            pmde_user=first['pmde_user'], jenis_tabel=unidentified, belum_qc=300,
        )
        client.force_login(first['pmde_user'])

        qc = self._section(client, 'qc', jenis_tabel=str(identified.pk))
        entries = _entries(qc)
        assert entries['Diidentifikasi']['baris'] == 500
        assert entries['Tidak Diidentifikasi']['baris'] == 0
        assert qc['baris'] == 500

    def test_the_rows_of_a_section_add_up_to_its_totals(self, client):
        """The per-PIC lines and the totals line are the same figures summed."""
        identified, unidentified, _unstructured = _seeded_kinds()
        first = _qc_bundle(jenis_tabel=identified, belum_qc=60)
        _qc_bundle(jenis_tabel=unidentified, belum_qc=25)
        client.force_login(_kasi_pmde_user())

        payload = self._summary(client)
        rows = payload['rows']
        assert len(rows) == 2
        assert sum(row['sections']['qc']['tikets'] for row in rows) == payload['qc']['tikets']
        assert sum(row['sections']['qc']['baris'] for row in rows) == payload['qc']['baris']
        assert first['pmde_user'].get_full_name() in {row['name'] for row in rows}

    def test_it_also_splits_by_the_kategori_wilayah_of_the_ilap(self, client):
        """The same tikets counted by reach rather than by handling."""
        regional = KategoriWilayah.objects.get(deskripsi='Regional')
        nasional = KategoriWilayah.objects.get(deskripsi='Nasional')
        first = _qc_bundle(belum_qc=500, kategori_wilayah=regional)
        _qc_bundle(pmde_user=first['pmde_user'], belum_qc=300, kategori_wilayah=regional)
        _qc_bundle(pmde_user=first['pmde_user'], belum_qc=40, kategori_wilayah=nasional)
        client.force_login(first['pmde_user'])

        qc = self._section(client, 'qc')
        entries = _entries(qc, 'kategori_wilayah')
        assert _counts(entries['Regional']) == {'name': 'Regional', 'tikets': 2, 'baris': 800}
        assert _counts(entries['Nasional']) == {'name': 'Nasional', 'tikets': 1, 'baris': 40}
        # Both splits account for the same headline, being the same tikets
        # counted two ways.
        assert sum(e['baris'] for e in qc['splits']['kategori_wilayah']) == qc['baris']
        assert sum(e['baris'] for e in qc['splits']['jenis_tabel']) == qc['baris']

    def test_a_tiket_matched_twice_by_a_join_is_counted_once(self, client):
        """Filtering through a to-many join must not double a breakdown row."""
        identified, _unidentified, _unstructured = _seeded_kinds()
        bundle = _qc_bundle(jenis_tabel=identified, belum_qc=500)
        sub_jenis_data = bundle['tiket'].id_periode_data.id_sub_jenis_data_ilap
        for label in ('DH A', 'DH B'):
            dasar_hukum = DasarHukum.objects.create(
                deskripsi=f'{label} {bundle["tiket"].pk}', kategori='PKS',
            )
            KlasifikasiJenisData.objects.create(
                id_sub_jenis_data=sub_jenis_data, id_klasifikasi_tabel=dasar_hukum,
            )
        client.force_login(bundle['pmde_user'])

        ids = ','.join(str(dh.pk) for dh in DasarHukum.objects.all())
        qc = self._section(client, 'qc', dasar_hukum=ids)
        assert _counts(_entries(qc)['Diidentifikasi']) == {
            'name': 'Diidentifikasi', 'tikets': 1, 'baris': 500,
        }


@pytest.mark.django_db
class TestSummarySelesai(SummaryEndpoint):
    """The quarter of finished work on the right of the table."""

    def test_counts_tikets_closed_inside_the_window(self, client):
        first = _selesai_bundle(days_ago=1, sudah_qc=250)
        _selesai_bundle(days_ago=89, pmde_user=first['pmde_user'], sudah_qc=150)
        client.force_login(first['pmde_user'])

        selesai = self._section(client, 'selesai')
        assert selesai['tikets'] == 2
        # The rows checked, which is the work the quarter actually took.
        assert selesai['baris'] == 400

    def test_a_tiket_closed_before_the_window_is_left_out(self, client):
        bundle = _selesai_bundle(days_ago=91)
        client.force_login(bundle['pmde_user'])
        assert self._section(client, 'selesai')['tikets'] == 0

    def test_a_tiket_still_in_the_queue_is_not_counted_as_finished(self, client):
        """The SELESAI action alone is not enough — a reopened tiket is where it
        is now, not where it has been."""
        bundle = _selesai_bundle(days_ago=2, status=STATUS_PENGENDALIAN_MUTU)
        client.force_login(bundle['pmde_user'])

        payload = self._summary(client)
        assert payload['selesai']['tikets'] == 0
        assert payload['qc']['tikets'] == 1

    def test_a_finished_tiket_without_the_action_is_left_out(self, client):
        """Closed before the log recorded it, so there is no date to place it by."""
        bundle = _selesai_bundle(days_ago=2, action=TiketActionType.PENGENDALIAN_MUTU)
        client.force_login(bundle['pmde_user'])
        assert self._section(client, 'selesai')['tikets'] == 0

    def test_it_splits_by_jenis_tabel_like_every_other_section(self, client):
        identified, unidentified, _unstructured = _seeded_kinds()
        first = _selesai_bundle(jenis_tabel=identified, sudah_qc=250)
        _selesai_bundle(
            pmde_user=first['pmde_user'], jenis_tabel=unidentified, sudah_qc=90,
        )
        client.force_login(first['pmde_user'])

        entries = _entries(self._section(client, 'selesai'))
        assert entries['Diidentifikasi']['baris'] == 250
        assert entries['Tidak Diidentifikasi']['baris'] == 90

    def test_it_lands_on_the_pic_line_and_follows_the_filter(self, client):
        first = _selesai_bundle()
        other = _selesai_bundle()
        client.force_login(_kasi_pmde_user())

        rows = {row['name']: row for row in self._summary(client)['rows']}
        assert rows[first['pmde_user'].get_full_name()]['sections']['selesai']['tikets'] == 1

        narrowed = self._summary(client, nomor_tiket=other['tiket'].nomor_tiket)
        assert [row['name'] for row in narrowed['rows']] == [
            other['pmde_user'].get_full_name()
        ]
        assert narrowed['selesai']['tikets'] == 1

    def test_the_jatuh_tempo_filter_leaves_it_alone(self, client):
        """Its deadline is long past, so the filter would empty it, not narrow it."""
        qc_bundle = _jatuh_tempo_bundle(5)
        _selesai_bundle(pmde_user=qc_bundle['pmde_user'])
        client.force_login(qc_bundle['pmde_user'])

        payload = self._summary(client, jatuh_tempo='10')
        assert payload['qc']['tikets'] == 1
        assert payload['selesai']['tikets'] == 1


@pytest.mark.django_db
class TestIndeksBeban(SummaryEndpoint):
    """The weighted load the table sorts by.

    Every case builds the same rows twice, differing in one factor, and asserts
    the ratio between the two loads — which is what the weights actually claim.
    The numbers themselves are meant to be edited, so nothing here pins one.
    """

    def _beban(self, client, **filters):
        return self._summary(client, **filters)['rows'][0]['beban']

    def test_the_tiket_count_does_not_enter_it(self, client):
        """QC is done row by row, so one large tiket is many small ones."""
        identified, _u, _t = _seeded_kinds()
        one = _qc_bundle(jenis_tabel=identified, belum_qc=900)
        client.force_login(one['pmde_user'])
        single = self._beban(client)

        split_user = _qc_bundle(jenis_tabel=identified, belum_qc=300)['pmde_user']
        for _ in range(2):
            _qc_bundle(pmde_user=split_user, jenis_tabel=identified, belum_qc=300)
        client.force_login(split_user)

        assert self._beban(client) == single

    def test_diidentifikasi_weighs_more_than_the_others(self, client):
        identified, unidentified, unstructured = _seeded_kinds()
        loads = {}
        for kind in (identified, unidentified, unstructured):
            bundle = _qc_bundle(jenis_tabel=kind, belum_qc=1000)
            client.force_login(bundle['pmde_user'])
            loads[kind.deskripsi] = self._beban(client)

        assert loads['Diidentifikasi'] > loads['Tidak Diidentifikasi']
        assert loads['Diidentifikasi'] > loads['Tidak Terstruktur']

    def test_regional_weighs_more_than_the_wider_reaches(self, client):
        loads = {}
        for name in ('Regional', 'Nasional', 'Internasional'):
            wilayah = KategoriWilayah.objects.get(deskripsi=name)
            bundle = _qc_bundle(kategori_wilayah=wilayah, belum_qc=1000)
            client.force_login(bundle['pmde_user'])
            loads[name] = self._beban(client)

        assert loads['Regional'] > loads['Nasional']
        assert loads['Regional'] > loads['Internasional']

    def test_prioritas_weighs_more(self, client):
        plain = _qc_bundle(with_prioritas=False, belum_qc=1000)
        client.force_login(plain['pmde_user'])
        without = self._beban(client)

        urgent = _qc_bundle(with_prioritas=True, belum_qc=1000)
        client.force_login(urgent['pmde_user'])

        assert self._beban(client) == pytest.approx(without * PRIORITAS_WEIGHT)

    def test_the_queue_in_hand_weighs_most(self, client):
        """The same rows count for less the further upstream they still are."""
        loads = {}
        in_hand = _qc_bundle(belum_qc=1000)
        client.force_login(in_hand['pmde_user'])
        loads['qc'] = self._beban(client)

        for key, status in (('pide', STATUS_IDENTIFIKASI), ('p3de', STATUS_DIREKAM)):
            bundle = _upstream_bundle(status, baris_lengkap=1000)
            client.force_login(bundle['pmde_user'])
            loads[key] = self._beban(client)

        done = _selesai_bundle(sudah_qc=1000)
        client.force_login(done['pmde_user'])
        loads['selesai'] = self._beban(client)

        assert loads['qc'] > loads['pide'] > loads['p3de'] > loads['selesai'] > 0

    def test_it_is_the_sum_of_every_queue(self, client):
        """A PIC's load is their whole line, not the queue this page lists."""
        bundle = _qc_bundle(belum_qc=1000)
        user = bundle['pmde_user']
        client.force_login(user)
        qc_only = self._beban(client)

        _upstream_bundle(STATUS_DIREKAM, pmde_user=user, baris_lengkap=1000)
        _selesai_bundle(pmde_user=user, sudah_qc=1000)

        assert self._beban(client) > qc_only

    def test_a_detail_line_carries_its_share_of_the_load(self, client):
        identified, unidentified, _t = _seeded_kinds()
        first = _qc_bundle(jenis_tabel=identified, belum_qc=1000)
        _qc_bundle(pmde_user=first['pmde_user'], jenis_tabel=unidentified, belum_qc=1000)
        client.force_login(first['pmde_user'])

        row = self._summary(client)['rows'][0]
        detail = dict(zip(
            [entry['name'] for entry in row['sections']['qc']['splits']['jenis_tabel']],
            row['detail']['jenis_tabel'],
        ))
        assert detail['Diidentifikasi'] > detail['Tidak Diidentifikasi'] > 0
        # The lines account for the PIC's own figure exactly.
        assert sum(row['detail']['jenis_tabel']) == row['beban']
        assert sum(row['detail']['kategori_wilayah']) == row['beban']

    def test_the_total_is_the_sum_of_the_lines(self, client):
        _qc_bundle(belum_qc=1000)
        _qc_bundle(belum_qc=500)
        client.force_login(_kasi_pmde_user())

        payload = self._summary(client)
        assert payload['beban'] == sum(row['beban'] for row in payload['rows'])

    def test_a_tiket_with_no_rows_left_adds_nothing(self, client):
        bundle = _qc_bundle(belum_qc=0)
        client.force_login(bundle['pmde_user'])
        assert self._beban(client) == 0

    def test_the_page_explains_how_it_is_worked_out(self, client):
        """The panel is built from the weights themselves, so a weight edited in
        the view changes what the page says about itself.

        Only the names are asserted, not the figures: they are rendered through
        the Indonesian locale, and pinning their formatting here would break on
        a setting that has nothing to do with the weights.
        """
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        html = client.get(reverse('quality_control')).content.decode()

        assert 'id="sq-beban-info"' in html
        assert 'Indeks Beban = ' in html
        for name in JENIS_TABEL_WEIGHTS:
            assert name in html
        for name in KATEGORI_WILAYAH_WEIGHTS:
            assert name in html
        assert 'Prioritas saat diterima' in html
        # Opened by its own control rather than shown outright.
        assert 'class="collapse sq-beban-info"' in html
        assert 'sq-beban-info-toggle' in html

    def test_the_filters_narrow_it(self, client):
        first = _qc_bundle(belum_qc=1000)
        _qc_bundle(pmde_user=first['pmde_user'], belum_qc=1000)
        client.force_login(first['pmde_user'])

        whole = self._beban(client)
        narrowed = self._beban(client, nomor_tiket=first['tiket'].nomor_tiket)
        assert narrowed == pytest.approx(whole / 2)


@pytest.mark.django_db
class TestSummaryPerPic(SummaryEndpoint):
    """The summary read one PIC PMDE at a time: the lines of the summary table."""

    def _rows(self, client, **filters):
        return {row['name']: row for row in self._summary(client, **filters)['rows']}

    def test_a_line_per_pic_carrying_every_section(self, client):
        mine = _qc_bundle()
        theirs = _qc_bundle()
        _upstream_bundle(STATUS_DIREKAM, pmde_user=theirs['pmde_user'], baris_lengkap=500)
        client.force_login(_kasi_pmde_user())

        rows = self._rows(client)
        assert set(rows) == {
            mine['pmde_user'].get_full_name(), theirs['pmde_user'].get_full_name(),
        }
        for row in rows.values():
            assert set(row['sections']) == {'qc', 'p3de', 'pide', 'selesai'}

        theirs_row = rows[theirs['pmde_user'].get_full_name()]
        assert theirs_row['sections']['qc']['baris'] == 60
        assert theirs_row['sections']['p3de']['baris'] == 500

    def test_a_pic_holding_nothing_in_a_section_reads_as_zeros(self, client):
        """Every line is the full width, or the figures would not line up."""
        with_qc = _qc_bundle()
        only_upstream = _upstream_bundle(STATUS_DIREKAM, baris_lengkap=500)
        client.force_login(_kasi_pmde_user())

        rows = self._rows(client)
        row = rows[only_upstream['pmde_user'].get_full_name()]
        assert row['sections']['qc']['tikets'] == 0
        assert row['sections']['qc']['baris'] == 0
        # Zeroed, not blank: the empty QC section still lists every jenis tabel,
        # in the order the line that does hold tikets lists them.
        held = rows[with_qc['pmde_user'].get_full_name()]['sections']['qc']
        for split in ('jenis_tabel', 'kategori_wilayah'):
            empty = row['sections']['qc']['splits'][split]
            assert [entry['name'] for entry in empty] == [
                entry['name'] for entry in held['splits'][split]
            ]
            assert all(entry['tikets'] == 0 for entry in empty)

    def test_each_line_splits_its_sections_by_jenis_tabel(self, client):
        identified, unidentified, _unstructured = _seeded_kinds()
        first = _qc_bundle(jenis_tabel=identified, belum_qc=60)
        _qc_bundle(pmde_user=first['pmde_user'], jenis_tabel=unidentified, belum_qc=10)
        client.force_login(first['pmde_user'])

        row = self._rows(client)[first['pmde_user'].get_full_name()]
        entries = _entries(row['sections']['qc'])
        assert _counts(entries['Diidentifikasi']) == {
            'name': 'Diidentifikasi', 'tikets': 1, 'baris': 60,
        }
        assert _counts(entries['Tidak Diidentifikasi']) == {
            'name': 'Tidak Diidentifikasi', 'tikets': 1, 'baris': 10,
        }

    def test_a_tiket_without_an_active_pic_gets_a_line_of_its_own(self, client):
        """Its work is real, so it is held apart rather than dropped."""
        bundle = _qc_bundle()
        TiketPIC.objects.filter(id_tiket=bundle['tiket']).update(active=False)
        client.force_login(_kasi_pmde_user())

        payload = self._summary(client)
        assert [row['name'] for row in payload['rows']] == ['Tanpa PIC PMDE']
        assert payload['rows'][0]['sections']['qc']['baris'] == payload['qc']['baris']
        # Nobody to lead to, so the line is text rather than a link.
        assert '<a ' not in payload['rows'][0]['pic']

    def test_lines_read_by_name_with_nobody_last(self, client):
        first = _qc_bundle()
        User.objects.filter(pk=first['pmde_user'].pk).update(
            first_name='Zulfa', last_name='',
        )
        second = _qc_bundle()
        User.objects.filter(pk=second['pmde_user'].pk).update(
            first_name='Ahmad', last_name='',
        )
        orphan = _qc_bundle()
        TiketPIC.objects.filter(id_tiket=orphan['tiket']).update(active=False)
        client.force_login(_kasi_pmde_user())

        assert [row['name'] for row in self._summary(client)['rows']] == [
            'Ahmad', 'Zulfa', 'Tanpa PIC PMDE',
        ]

    def test_the_lines_follow_the_filter_panel(self, client):
        """Which PIC appear is read off the filtered sections, not the roster."""
        first = _qc_bundle()
        second = _qc_bundle()
        client.force_login(_kasi_pmde_user())

        assert len(self._summary(client)['rows']) == 2
        rows = self._summary(client, nomor_tiket=second['tiket'].nomor_tiket)['rows']
        assert [row['name'] for row in rows] == [second['pmde_user'].get_full_name()]
        assert first['pmde_user'].get_full_name() != second['pmde_user'].get_full_name()

    def test_a_name_links_to_the_profil_the_reader_may_open(self, client):
        bundle = _qc_bundle()
        client.force_login(_kasi_pmde_user())

        row = self._summary(client)['rows'][0]
        assert f'/profil-pic/{bundle["pmde_user"].username}/' in row['pic']

    def test_the_page_heads_the_table_with_the_reference_jenis_tabel(self, client):
        """The detail lines are the reference table, so a new kind gets a line.

        Nothing else ties the names to the figures beside them: both are built
        from `jenis_tabel_kinds`, and a list spelled out in the markup would
        silently mislabel every line the day a jenis tabel is added.
        """
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        html = client.get(reverse('quality_control')).content.decode()

        for label in ('Beban Kerja', 'Nama PIC', 'Proses QC', 'Masih di P3DE',
                      'Masih di PIDE', 'Selesai QC 90 Hari Terakhir',
                      'Tiket', 'Baris Data', 'Jenis Tabel', 'Kategori Wilayah'):
            assert label in html
        for kind in JenisTabel.objects.values_list('deskripsi', flat=True):
            assert kind in html
        for wilayah in KategoriWilayah.objects.values_list('deskripsi', flat=True):
            assert wilayah in html
        # The JS fills a line's cells in this order; the header above them was
        # rendered from the same list.
        assert 'data-summary-sections="qc,p3de,pide,selesai"' in html
        assert 'data-summary-variants="own,upstream,upstream-alt,done"' in html
        # The table opens on the heaviest QC load rather than alphabetically.
        assert 'data-summary-sort="beban" data-summary-sort-desc="1"' in html
