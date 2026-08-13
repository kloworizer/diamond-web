"""Tests for views/identifikasi.py (view + data endpoint).

The page is the one `seksi_queue` builds, so the filter machinery it shares with
Quality Control is covered by test_quality_control_view.py and not repeated here.
What is tested is what the Identifikasi page decides for itself: whose queue it
shows, which dates its deadline counts from, and that its three figures are the
identification split rather than the QC one.
"""
from datetime import date, datetime, timedelta
from itertools import count

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.constants.tiket_status import (
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_DIREKAM,
    STATUS_DITELITI,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
)
from diamond_web.models import TiketPIC
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


def _pide_admin_user():
    return UserFactory(is_superuser=True)


def _kasi_pide_user():
    """A supervisor, who sees the whole seksi's queue rather than only their own."""
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='kasi_pide')
    user.groups.add(group)
    return user


_UNSET = object()
_PENYAMPAIAN_SEQ = count()


def _pide_bundle(with_durasi=True, with_prioritas=False, tgl_kirim_pide=None,
                 pide_user=None, tgl_rekam_pide=_UNSET, durasi=10,
                 jenis_tabel=None, status_tiket=STATUS_IDENTIFIKASI,
                 baris_lengkap=100, split=(30, 10, 0, 0)):
    """A tiket being identified, with its PIC PIDE and a PIDE durasi behind it.

    `split` is the (I, U, CDE, Res) identification has recorded so far, so the
    rows left to identify are `baris_lengkap` minus its sum.
    """
    jenis_tabel = jenis_tabel or JenisTabelFactory()
    jenis_data = JenisDataILAPFactory(id_jenis_tabel=jenis_tabel)
    # periode_penyampaian is unique and the factory draws it from a small word
    # list, so bundles created side by side collide unless it is spelled out.
    periode_data = PeriodeJenisDataFactory(
        id_sub_jenis_data_ilap=jenis_data,
        id_periode_pengiriman=PeriodePengirimanFactory(
            periode_penyampaian=f'ID {next(_PENYAMPAIAN_SEQ)}',
        ),
    )
    tgl_kirim_pide = tgl_kirim_pide or datetime.now() - timedelta(days=5)
    # Anchored to mid-morning: the deadline counts from tgl_rekam_pide, so a run
    # late in the evening would otherwise push it onto the following day.
    tgl_kirim_pide = tgl_kirim_pide.replace(hour=9, minute=0, second=0, microsecond=0)
    if tgl_rekam_pide is _UNSET:
        tgl_rekam_pide = tgl_kirim_pide + timedelta(hours=2)
    baris_i, baris_u, baris_cde, baris_res = split
    tiket = TiketFactory(
        id_periode_data=periode_data,
        status_tiket=status_tiket,
        tgl_kirim_pide=tgl_kirim_pide,
        tgl_rekam_pide=tgl_rekam_pide,
        baris_lengkap=baris_lengkap,
        baris_i=baris_i,
        baris_u=baris_u,
        baris_cde=baris_cde,
        baris_res=baris_res,
    )
    group, _ = Group.objects.get_or_create(name='user_pide')
    if pide_user is None:
        pide_user = UserFactory()
    pide_user.groups.add(group)
    TiketPICFactory(id_tiket=tiket, id_user=pide_user, role=TiketPIC.Role.PIDE, active=True)

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

    return {
        'tiket': tiket,
        'jenis_data': jenis_data,
        'jenis_tabel': jenis_tabel,
        'pide_user': pide_user,
        'group': group,
    }


def _jatuh_tempo_bundle(days, **kwargs):
    """A bundle whose jatuh tempo is `days` days from today, negative allowed.

    The deadline counts the durasi from tgl_kirim_pide, which `_pide_bundle`
    puts five days back, so the durasi that lands the deadline on the wanted day
    is that gap plus those five days.
    """
    return _pide_bundle(durasi=days + 5, **kwargs)


@pytest.mark.django_db
class TestIdentifikasiView:
    def test_get_denied_for_non_pide(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse('identifikasi'))
        assert resp.status_code == 403

    def test_get_success(self, client):
        client.force_login(_pide_admin_user())
        resp = client.get(reverse('identifikasi'))
        assert resp.status_code == 200

    def test_kasi_pide_may_open_the_page(self, client):
        client.force_login(_kasi_pide_user())
        resp = client.get(reverse('identifikasi'))
        assert resp.status_code == 200

    def test_page_names_the_payload_keys_the_endpoint_sends(self, client):
        """The shared template reads its variable columns out of a config block.

        Nothing else ties the two halves together, so a key renamed on one side
        would silently blank a column; this is what notices.
        """
        bundle = _pide_bundle()
        client.force_login(bundle['pide_user'])
        html = client.get(reverse('identifikasi')).content.decode()
        row = client.get(
            reverse('identifikasi_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        ).json()['data'][0]

        for key in ('pic_pide', 'tgl_kirim_pide', 'tgl_rekam_pide',
                    'jml_baris_lengkap', 'jml_selesai', 'jml_progress'):
            assert f"'{key}'" in html
            assert key in row


@pytest.mark.django_db
class TestIdentifikasiData:
    url = 'identifikasi_data'

    def _rows(self, client, **params):
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', **params},
        )
        assert resp.status_code == 200
        return resp.json()

    def test_denied_for_non_pide(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse(self.url))
        assert resp.status_code == 302

    def test_basic_row(self, client):
        bundle = _pide_bundle(with_prioritas=True)
        client.force_login(bundle['pide_user'])
        row = self._rows(client)['data'][0]
        assert row['nomor_tiket'] == bundle['tiket'].nomor_tiket
        assert row['prioritas'] == 'Ya'
        # 40 of the 100 rows have been split into I/U/CDE/Res so far.
        assert row['jml_baris_lengkap'] == 100
        assert row['jml_selesai'] == 40
        assert row['jml_progress'] == 60
        assert row['deadline']['display'] != '-'
        assert row['sisa_hari'] is not None

    def test_a_split_beyond_baris_lengkap_leaves_nothing_to_identify(self, client):
        """Counts that disagree are not negative work left."""
        bundle = _pide_bundle(baris_lengkap=50, split=(40, 20, 0, 0))
        client.force_login(bundle['pide_user'])
        row = self._rows(client)['data'][0]
        assert row['jml_progress'] == 0
        assert row['jml_selesai'] == 50

    def test_unstarted_identification_leaves_every_row_to_do(self, client):
        bundle = _pide_bundle(split=(0, 0, 0, 0))
        client.force_login(bundle['pide_user'])
        row = self._rows(client)['data'][0]
        assert row['jml_selesai'] == 0
        assert row['jml_progress'] == 100

    def test_no_durasi_means_no_deadline(self, client):
        bundle = _pide_bundle(with_durasi=False)
        client.force_login(bundle['pide_user'])
        row = self._rows(client)['data'][0]
        assert row['deadline'] == {'display': '-', 'sort': ''}
        assert row['jatuh_tempo']['display'] == '-'
        assert row['sisa_hari'] is None

    def test_deadline_counts_from_tgl_rekam_pide_when_it_is_set(self, client):
        kirim = datetime.now() - timedelta(days=20)
        rekam = datetime.now() - timedelta(days=3)
        bundle = _pide_bundle(tgl_kirim_pide=kirim, tgl_rekam_pide=rekam, durasi=10)
        client.force_login(bundle['pide_user'])
        row = self._rows(client)['data'][0]
        expected = rekam.date() + timedelta(days=10)
        assert row['deadline']['display'] == expected.strftime('%d/%m/%Y')
        assert row['sisa_hari'] == (expected - date.today()).days

    def test_deadline_falls_back_to_tgl_kirim_pide(self, client):
        """A tiket PIDE has not opened yet still counts from the day it arrived."""
        kirim = datetime.now() - timedelta(days=20)
        bundle = _pide_bundle(tgl_kirim_pide=kirim, tgl_rekam_pide=None, durasi=10)
        client.force_login(bundle['pide_user'])
        row = self._rows(client)['data'][0]
        expected = kirim.date() + timedelta(days=10)
        assert row['deadline']['display'] == expected.strftime('%d/%m/%Y')

    def test_durasi_is_the_one_active_at_the_rekam_date(self, client):
        """The durasi row is picked by tgl_rekam_pide, not by the older arrival."""
        kirim = datetime.now() - timedelta(days=40)
        rekam = datetime.now() - timedelta(days=2)
        bundle = _pide_bundle(
            tgl_kirim_pide=kirim, tgl_rekam_pide=rekam, with_durasi=False,
        )
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=bundle['jenis_data'], seksi=bundle['group'],
            durasi=5, start_date=date(2000, 1, 1),
            end_date=(kirim + timedelta(days=1)).date(),
        )
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=bundle['jenis_data'], seksi=bundle['group'],
            durasi=30, start_date=(kirim + timedelta(days=2)).date(), end_date=None,
        )
        client.force_login(bundle['pide_user'])
        row = self._rows(client)['data'][0]
        expected = rekam.date() + timedelta(days=30)
        assert row['deadline']['display'] == expected.strftime('%d/%m/%Y')

    def test_a_pmde_durasi_is_not_pide_s(self, client):
        """The deadline reads its own seksi's rows only."""
        bundle = _pide_bundle(with_durasi=False)
        pmde_group, _ = Group.objects.get_or_create(name='user_pmde')
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=bundle['jenis_data'], seksi=pmde_group,
            durasi=30, start_date=date(2000, 1, 1), end_date=None,
        )
        client.force_login(bundle['pide_user'])
        row = self._rows(client)['data'][0]
        assert row['deadline']['display'] == '-'

    def test_only_shows_the_readers_own_tikets(self, client):
        mine = _pide_bundle()
        _pide_bundle()
        client.force_login(mine['pide_user'])
        payload = self._rows(client)
        assert [row['nomor_tiket'] for row in payload['data']] == [
            mine['tiket'].nomor_tiket
        ]

    def test_kasi_sees_the_whole_seksi(self, client):
        first = _pide_bundle()
        second = _pide_bundle()
        client.force_login(_kasi_pide_user())
        payload = self._rows(client)
        assert {row['nomor_tiket'] for row in payload['data']} == {
            first['tiket'].nomor_tiket, second['tiket'].nomor_tiket,
        }

    @pytest.mark.parametrize('status', [
        STATUS_DIKIRIM_KE_PIDE, STATUS_PENGENDALIAN_MUTU, STATUS_DIREKAM,
    ])
    def test_only_tikets_being_identified_are_listed(self, client, status):
        bundle = _pide_bundle(status_tiket=status)
        client.force_login(bundle['pide_user'])
        assert self._rows(client)['data'] == []

    @pytest.mark.parametrize('order_col', ['0', '4', '6', '8', '9', '10'])
    def test_ordering(self, client, order_col):
        bundle = _pide_bundle()
        client.force_login(bundle['pide_user'])
        payload = self._rows(
            client, **{'order[0][column]': order_col, 'order[0][dir]': 'desc'},
        )
        assert len(payload['data']) == 1

    def test_ordering_invalid_column_falls_back(self, client):
        bundle = _pide_bundle()
        client.force_login(bundle['pide_user'])
        payload = self._rows(client, **{'order[0][column]': 'abc'})
        assert len(payload['data']) == 1

    def test_post_method(self, client):
        bundle = _pide_bundle()
        client.force_login(bundle['pide_user'])
        resp = client.post(reverse(self.url), {'draw': '2', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 2


@pytest.mark.django_db
class TestIdentifikasiFilters:
    url = 'identifikasi_data'

    def _rows(self, client, **params):
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', **params},
        )
        return resp.json()

    def _options(self, client, **params):
        resp = client.get(reverse(self.url), {'get_filter_options': '1', **params})
        return resp.json()['filter_options']

    def test_filter_by_nomor_tiket(self, client):
        first = _pide_bundle()
        second = _pide_bundle(pide_user=None)
        kasi = _kasi_pide_user()
        client.force_login(kasi)
        payload = self._rows(client, nomor_tiket=first['tiket'].nomor_tiket)
        assert [row['nomor_tiket'] for row in payload['data']] == [
            first['tiket'].nomor_tiket
        ]
        assert payload['recordsFiltered'] == 1
        assert second['tiket'].nomor_tiket not in {
            row['nomor_tiket'] for row in payload['data']
        }

    def test_filter_by_pic_pide(self, client):
        mine = _pide_bundle()
        _pide_bundle()
        client.force_login(_kasi_pide_user())
        payload = self._rows(client, pic_pide=str(mine['pide_user'].id))
        assert [row['nomor_tiket'] for row in payload['data']] == [
            mine['tiket'].nomor_tiket
        ]

    def test_filter_jatuh_tempo_thresholds(self, client):
        near = _jatuh_tempo_bundle(5)
        far = _jatuh_tempo_bundle(40)
        client.force_login(_kasi_pide_user())

        under_ten = self._rows(client, jatuh_tempo='10')['data']
        assert [row['nomor_tiket'] for row in under_ten] == [near['tiket'].nomor_tiket]

        under_sixty = self._rows(client, jatuh_tempo='60')['data']
        assert {row['nomor_tiket'] for row in under_sixty} == {
            near['tiket'].nomor_tiket, far['tiket'].nomor_tiket,
        }

    def test_filter_options_cover_every_dropdown(self, client):
        bundle = _pide_bundle()
        client.force_login(bundle['pide_user'])
        options = self._options(client)
        assert {o['id'] for o in options['nomor_tiket']} == {bundle['tiket'].nomor_tiket}
        assert [o['id'] for o in options['jatuh_tempo']] == ['10', '30', '60']
        assert {o['id'] for o in options['pic_pide']} == {str(bundle['pide_user'].id)}


@pytest.mark.django_db
class TestIdentifikasiSummary:
    url = 'identifikasi_data'

    def _summary(self, client, **params):
        resp = client.get(reverse(self.url), {'get_summary': '1', **params})
        assert resp.status_code == 200
        return resp.json()

    def test_own_section_counts_the_rows_left_to_identify(self, client):
        bundle = _pide_bundle(baris_lengkap=100, split=(30, 10, 0, 0))
        client.force_login(bundle['pide_user'])
        payload = self._summary(client)
        assert payload['identifikasi']['tikets'] == 1
        assert payload['identifikasi']['baris'] == 60
        assert payload['dikirim_ke_pide']['tikets'] == 0
        assert payload['p3de']['tikets'] == 0

    def test_a_received_tiket_lands_in_the_upstream_pide_section_only(self, client):
        bundle = _pide_bundle(
            status_tiket=STATUS_DIKIRIM_KE_PIDE, baris_lengkap=80, split=(0, 0, 0, 0),
        )
        client.force_login(bundle['pide_user'])
        payload = self._summary(client)
        assert payload['dikirim_ke_pide']['tikets'] == 1
        # Nothing has been split yet, so baris lengkap is the only count there is.
        assert payload['dikirim_ke_pide']['baris'] == 80
        assert payload['identifikasi']['tikets'] == 0
        assert payload['p3de']['tikets'] == 0

    @pytest.mark.parametrize('status', [STATUS_DIREKAM, STATUS_DITELITI])
    def test_a_p3de_tiket_lands_in_the_p3de_section_only(self, client, status):
        bundle = _pide_bundle(status_tiket=status, baris_lengkap=70, split=(0, 0, 0, 0))
        client.force_login(bundle['pide_user'])
        payload = self._summary(client)
        assert payload['p3de']['tikets'] == 1
        assert payload['p3de']['baris'] == 70
        assert payload['identifikasi']['tikets'] == 0
        assert payload['dikirim_ke_pide']['tikets'] == 0

    def test_every_section_lists_every_jenis_tabel(self, client):
        other = JenisTabelFactory()
        bundle = _pide_bundle()
        client.force_login(bundle['pide_user'])
        payload = self._summary(client)
        names = [entry['name'] for entry in payload['identifikasi']['breakdown']]
        assert bundle['jenis_tabel'].deskripsi in names
        assert other.deskripsi in names
        for section in ('identifikasi', 'dikirim_ke_pide', 'p3de'):
            assert [entry['name'] for entry in payload[section]['breakdown']] == names

    def test_jatuh_tempo_filter_leaves_the_upstream_sections_alone(self, client):
        """An upstream tiket has no deadline yet, so the threshold cannot hide it."""
        _jatuh_tempo_bundle(2)
        upstream = _pide_bundle(status_tiket=STATUS_DIREKAM)
        client.force_login(_kasi_pide_user())
        payload = self._summary(client, jatuh_tempo='10')
        assert payload['identifikasi']['tikets'] == 1
        assert payload['p3de']['tikets'] == 1
        assert payload['p3de']['baris'] == upstream['tiket'].baris_lengkap


@pytest.mark.django_db
class TestIdentifikasiChart:
    url = 'identifikasi_data'

    def _chart(self, client, **params):
        resp = client.get(reverse(self.url), {'get_chart_data': '1', **params})
        assert resp.status_code == 200
        return resp.json()

    def test_series_are_grouped_per_pic_pide(self, client):
        first = _jatuh_tempo_bundle(10)
        _jatuh_tempo_bundle(20, pide_user=None)
        client.force_login(_kasi_pide_user())
        payload = self._chart(client)
        assert payload['categories'] == ['10 hari', '20 hari']
        assert len(payload['series']) == 2
        first_series = next(
            s for s in payload['series']
            if s['name'] == first['pide_user'].get_full_name()
        )
        # 60 rows left to identify, all falling due on the same day.
        assert first_series['data'] == [60, 0]

    def test_progress_of_the_same_pic_is_summed_per_jatuh_tempo(self, client):
        user = UserFactory()
        _jatuh_tempo_bundle(10, pide_user=user)
        _jatuh_tempo_bundle(10, pide_user=user)
        client.force_login(_kasi_pide_user())
        payload = self._chart(client)
        assert payload['categories'] == ['10 hari']
        assert payload['series'][0]['data'] == [120]

    def test_tiket_without_a_deadline_is_left_out(self, client):
        bundle = _pide_bundle(with_durasi=False)
        client.force_login(bundle['pide_user'])
        payload = self._chart(client)
        assert payload['categories'] == []
        assert payload['series'] == []

    def test_tiket_without_an_active_pic_gets_its_own_series(self, client):
        bundle = _jatuh_tempo_bundle(10)
        TiketPIC.objects.filter(
            id_tiket=bundle['tiket'], role=TiketPIC.Role.PIDE,
        ).update(active=False)
        client.force_login(_kasi_pide_user())
        payload = self._chart(client)
        assert [s['name'] for s in payload['series']] == ['Tanpa PIC PIDE']
