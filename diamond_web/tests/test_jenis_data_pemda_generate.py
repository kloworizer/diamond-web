"""Tests for the PD/PV jenis data generator (views/jenis_data_pemda_generate.py)."""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.models import JenisDataILAP
from diamond_web.tests.conftest import (
    ILAPFactory, JenisDataILAPFactory, JenisTabelFactory, StatusDataFactory, UserFactory,
)


def _user(*groups):
    user = UserFactory()
    for name in groups:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


@pytest.fixture
def world(db):
    """Eligible PD001-PD003 + PV001, plus ILAPs every exclusion rule must drop.

    Kode 4101 already exists on PD001 only.
    """
    names = {
        'PD001': 'Kabupaten Serang', 'PD002': 'Kota Bekasi', 'PD003': 'kabupaten tegal',
        'PV001': 'Provinsi Bali',
        'PDX01': 'Kabupaten Kode Aneh',          # code not P[DV]nnn
        'PD004': 'PD004',                        # no kabupaten/kota/provinsi
        'PD005': 'Kotawaringin Timur',           # "kota" only inside a word
        'PV002': 'Provinsi DKI Jakarta',         # Jakarta
        'PD006': 'Kota Administrasi Jakarta Selatan',
        'KM001': 'Kota Bukan Pemda',             # not a PD/PV ILAP at all
    }
    ilaps = {code: ILAPFactory(id_ilap=code, nama_ilap=nama) for code, nama in names.items()}
    tabel = JenisTabelFactory()
    status = StatusDataFactory()
    JenisDataILAPFactory(
        id_ilap=ilaps['PD001'], id_jenis_data='PD00141', id_sub_jenis_data='PD0014101',
        nama_jenis_data='Surat TDP', nama_sub_jenis_data='Surat TDP',
        nama_tabel_I='TBL_NIB', nama_tabel_U='TBL_NIB_U', id_jenis_tabel=tabel, id_status_data=status,
    )
    return {'ilaps': ilaps, 'tabel': tabel, 'status': status}


@pytest.fixture
def admin_p3de(client):
    user = _user('admin_p3de')
    client.force_login(user)
    return user


def _form(world, **overrides):
    data = {
        'kode': '4101', 'scope': 'ALL',
        'nama_jenis_data': 'Surat TDP', 'nama_sub_jenis_data': 'Surat TDP',
        'nama_tabel_I': 'TBL_NIB', 'nama_tabel_U': 'TBL_NIB_U',
        'id_jenis_tabel': world['tabel'].pk, 'id_status_data': world['status'].pk,
    }
    data.update(overrides)
    return data


def _key(world, code):
    return f"ilap-{world['ilaps'][code].pk}"


@pytest.mark.django_db
class TestAccess:
    def test_non_admin_forbidden(self, client, world):
        client.force_login(_user('user_p3de'))
        assert client.get(reverse('jenis_data_pemda_generate')).status_code == 403
        assert client.post(reverse('jenis_data_pemda_preview'), _form(world)).status_code == 403
        assert client.post(reverse('jenis_data_pemda_execute'), _form(world, selected=['x'])).status_code == 403

    def test_admin_p3de_page(self, client, admin_p3de, world):
        resp = client.get(reverse('jenis_data_pemda_generate'))
        assert resp.status_code == 200
        assert resp.context['total_ilap_pd'] == 3  # PD001-003
        assert resp.context['total_ilap_pv'] == 1
        assert resp.context['total_ilap_dikecualikan'] == 5
        html = resp.content.decode()
        assert '{#' not in html and '{%' not in html

    def test_kode_options_count_what_is_left_to_generate(self, client, admin_p3de, world):
        # 4102 on every eligible ILAP (plus the excluded Jakarta one, which must
        # not count as "still missing").
        for code in ('PD001', 'PD002', 'PD003', 'PV001', 'PV002'):
            JenisDataILAPFactory(id_ilap=world['ilaps'][code], id_jenis_data=f'{code}41',
                                 id_sub_jenis_data=f'{code}4102')
        options = client.get(reverse('jenis_data_pemda_generate')).context['generate_options']
        by_kode = {o['kode']: o for o in options['kode']}
        assert (by_kode['4101']['belum_PD'], by_kode['4101']['belum_PV']) == (2, 1)
        assert (by_kode['4102']['belum_PD'], by_kode['4102']['belum_PV']) == (0, 0)
        assert options['total'] == {'PD': 3, 'PV': 1}

    def test_kode_only_at_excluded_ilaps_is_hidden(self, client, admin_p3de, world):
        # 7401 only at the Jakarta ILAP, 9901 only at an ILAP not named as a
        # region; 4101 also at Jakarta but carried by PD001 too.
        for code, kode in (('PV002', '7401'), ('PD004', '9901'), ('PV002', '4101')):
            JenisDataILAPFactory(id_ilap=world['ilaps'][code], id_jenis_data=f'{code}{kode[:2]}',
                                 id_sub_jenis_data=f'{code}{kode}')
        options = client.get(reverse('jenis_data_pemda_generate')).context['generate_options']
        offered = {o['kode'] for o in options['kode']}
        assert '7401' not in offered and '9901' not in offered
        assert '4101' in offered
        assert sorted(options['kode_dikecualikan']) == ['7401', '9901']

    def test_list_page_links_to_generator(self, client, admin_p3de, world):
        html = client.get(reverse('jenis_data_ilap_list')).content.decode()
        assert reverse('jenis_data_pemda_generate') in html


@pytest.mark.django_db
class TestTemplate:
    def test_defaults_from_existing_rows(self, client, admin_p3de, world):
        body = client.get(reverse('jenis_data_pemda_template'), {'kode': '4101', 'scope': 'ALL'}).json()
        assert body['kode_baru'] is False
        assert body['sudah_ada_pd'] == 1 and body['sudah_ada_pv'] == 0
        assert body['ilap_in_scope'] == 4
        assert body['belum_ada_in_scope'] == 3
        assert body['dikecualikan_in_scope'] == 5
        assert body['defaults']['nama_tabel_I'] == 'TBL_NIB'
        assert body['defaults']['id_jenis_tabel'] == world['tabel'].pk

    def test_new_kode(self, client, admin_p3de, world):
        body = client.get(reverse('jenis_data_pemda_template'), {'kode': '9501'}).json()
        assert body['kode_baru'] is True
        assert body['defaults']['nama_jenis_data'] == ''

    @pytest.mark.parametrize('kode', ['0001', '4100', '41a1', '41011', ''])
    def test_invalid_kode(self, client, admin_p3de, world, kode):
        resp = client.get(reverse('jenis_data_pemda_template'), {'kode': kode})
        assert resp.status_code == 400


@pytest.mark.django_db
class TestPreview:
    def test_lists_missing_ilaps_only_and_writes_nothing(self, client, admin_p3de, world):
        before = JenisDataILAP.objects.count()
        body = client.post(reverse('jenis_data_pemda_preview'), _form(world)).json()
        assert [r['id_sub_jenis_data'] for r in body['rows']] == ['PD0024101', 'PD0034101', 'PV0014101']
        assert body['rows'][0]['id_jenis_data'] == 'PD00241'
        assert body['total_sudah_ada'] == 1
        assert body['sudah_ada'] == ['PD001 - Kabupaten Serang (PD0014101)']
        excluded = {d.split(' - ')[0]: d for d in body['dikecualikan']}
        assert set(excluded) == {'PDX01', 'PD004', 'PD005', 'PV002', 'PD006'}
        assert 'tidak berpola' in excluded['PDX01']
        assert 'Kabupaten/Kota/Provinsi' in excluded['PD004']
        assert 'Kabupaten/Kota/Provinsi' in excluded['PD005']
        assert 'Jakarta' in excluded['PV002'] and 'Jakarta' in excluded['PD006']
        assert JenisDataILAP.objects.count() == before

    def test_scope_pv(self, client, admin_p3de, world):
        body = client.post(reverse('jenis_data_pemda_preview'), _form(world, scope='PV')).json()
        assert [r['id_sub_jenis_data'] for r in body['rows']] == ['PV0014101']

    def test_warns_when_jenis_data_used_with_other_name(self, client, admin_p3de, world):
        JenisDataILAPFactory(id_ilap=world['ilaps']['PD002'], id_jenis_data='PD00241',
                             id_sub_jenis_data='PD0024102', nama_jenis_data='Sesuatu Lain')
        rows = {r['id_sub_jenis_data']: r for r in
                client.post(reverse('jenis_data_pemda_preview'), _form(world)).json()['rows']}
        assert rows['PD0024101']['status'] == 'peringatan'
        assert 'Sesuatu Lain' in rows['PD0024101']['keterangan']
        assert rows['PD0034101']['status'] == 'baru'

    def test_same_name_different_case_is_not_a_warning(self, client, admin_p3de, world):
        JenisDataILAPFactory(id_ilap=world['ilaps']['PD002'], id_jenis_data='PD00241',
                             id_sub_jenis_data='PD0024102', nama_jenis_data='SURAT  tdp')
        rows = {r['id_sub_jenis_data']: r for r in
                client.post(reverse('jenis_data_pemda_preview'), _form(world)).json()['rows']}
        assert rows['PD0024101']['status'] == 'baru'

    @pytest.mark.parametrize('field,value', [
        ('nama_jenis_data', '  '), ('nama_sub_jenis_data', ''), ('id_jenis_tabel', ''),
        ('id_status_data', '99999'), ('nama_tabel_I', 'x' * 256), ('scope', 'XX'),
    ])
    def test_invalid_form(self, client, admin_p3de, world, field, value):
        resp = client.post(reverse('jenis_data_pemda_preview'), _form(world, **{field: value}))
        assert resp.status_code == 400
        assert resp.json()['message']


@pytest.mark.django_db
class TestExecute:
    def test_creates_selected_rows_with_derived_ids(self, client, admin_p3de, world):
        resp = client.post(reverse('jenis_data_pemda_execute'), _form(
            world, nama_sub_jenis_data='  Surat   TDP Baru ',
            selected=[_key(world, 'PD002'), _key(world, 'PV001')]))
        body = resp.json()
        assert [c['id_sub_jenis_data'] for c in body['created']] == ['PD0024101', 'PV0014101']
        assert body['created'][0]['profil_url'] == reverse('jenis_data_ilap_profil', args=['PD0024101'])

        jd = JenisDataILAP.objects.get(id_sub_jenis_data='PV0014101')
        assert jd.id_ilap == world['ilaps']['PV001']
        assert jd.id_jenis_data == 'PV00141'
        assert jd.nama_sub_jenis_data == 'Surat TDP Baru'  # whitespace collapsed
        assert jd.nama_tabel_U == 'TBL_NIB_U'
        assert jd.id_jenis_tabel == world['tabel'] and jd.id_status_data == world['status']
        assert jd.create_by == admin_p3de.username[:9]
        # Not ticked -> not created.
        assert not JenisDataILAP.objects.filter(id_sub_jenis_data='PD0034101').exists()

    def test_code_created_meanwhile_is_skipped_not_duplicated(self, client, admin_p3de, world):
        JenisDataILAPFactory(id_ilap=world['ilaps']['PD002'], id_jenis_data='PD00241',
                             id_sub_jenis_data='PD0024101', nama_jenis_data='Surat TDP')
        body = client.post(reverse('jenis_data_pemda_execute'), _form(
            world, selected=[_key(world, 'PD002'), _key(world, 'PD003')])).json()
        assert [c['id_sub_jenis_data'] for c in body['created']] == ['PD0034101']
        assert body['skipped'] == 1
        assert JenisDataILAP.objects.filter(id_sub_jenis_data='PD0024101').count() == 1

    @pytest.mark.parametrize('code', ['PDX01', 'PD004', 'PD005', 'PV002', 'PD006'])
    def test_excluded_ilap_never_created_even_if_posted(self, client, admin_p3de, world, code):
        body = client.post(reverse('jenis_data_pemda_execute'), _form(world, selected=[_key(world, code)])).json()
        assert body['created'] == []
        assert not JenisDataILAP.objects.filter(id_ilap=world['ilaps'][code]).exists()

    @pytest.mark.parametrize('code,kode', [('PV002', '7401'), ('PD004', '9901')])
    def test_kode_only_at_excluded_ilaps_rejected_everywhere(self, client, admin_p3de, world, code, kode):
        JenisDataILAPFactory(id_ilap=world['ilaps'][code], id_jenis_data=f'{code}{kode[:2]}',
                             id_sub_jenis_data=f'{code}{kode}')
        before = JenisDataILAP.objects.count()
        responses = [
            client.get(reverse('jenis_data_pemda_template'), {'kode': kode}),
            client.post(reverse('jenis_data_pemda_preview'), _form(world, kode=kode)),
            client.post(reverse('jenis_data_pemda_execute'), _form(world, kode=kode, selected=[_key(world, 'PD002')])),
        ]
        for resp in responses:
            assert resp.status_code == 400
            assert 'hanya dipakai ILAP yang dikecualikan' in resp.json()['message']
        assert JenisDataILAP.objects.count() == before

    def test_kode_shared_with_excluded_ilap_still_allowed(self, client, admin_p3de, world):
        JenisDataILAPFactory(id_ilap=world['ilaps']['PV002'], id_jenis_data='PV00241',
                             id_sub_jenis_data='PV0024101')
        body = client.post(reverse('jenis_data_pemda_execute'), _form(
            world, selected=[_key(world, 'PD002')])).json()
        assert [c['id_sub_jenis_data'] for c in body['created']] == ['PD0024101']

    def test_requires_selection(self, client, admin_p3de, world):
        assert client.post(reverse('jenis_data_pemda_execute'), _form(world)).status_code == 400
