"""Tanda Terima scoped per Kanwil / ND Pengantar.

Covers the two mapping shapes a regional ILAP can have — kategori PD reaching
a Kanwil through a KPP, and kategori PV mapped straight to a Kanwil because it
has no KPP counterpart — plus the nasional/internasional flow that stays keyed
on the ILAP itself.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from diamond_web.models import (
    DetilTandaTerima,
    ILAPKPP,
    TandaTerimaData,
    Tiket,
    TiketPIC,
)
from diamond_web.utils.tanda_terima_scope import (
    nasional_ilap_queryset,
    nd_pengantar_options,
    regional_ilap_queryset,
    scoped_tiket_queryset,
)

from .conftest import (
    ILAPFactory,
    KanwilFactory,
    KPPFactory,
    PeriodeJenisDataFactory,
    PeriodePengirimanFactory,
    TiketFactory,
    TiketPICFactory,
)


ND_SATU = 'B-901/KANWIL/06/2026'
ND_DUA = 'B-902/KANWIL/07/2026'


def _tiket(ilap, nomor_nd, periode_pengiriman, user=None, status=1):
    """Create a tiket for `ilap` delivered under `nomor_nd`.

    `periode_pengiriman` is shared across the fixture: the factory draws its
    unique `periode_penyampaian` from a random word, so building one per tiket
    collides sooner or later.
    """
    periode_data = PeriodeJenisDataFactory(
        id_sub_jenis_data_ilap__id_ilap=ilap,
        id_periode_pengiriman=periode_pengiriman,
    )
    tiket = TiketFactory(
        id_periode_data=periode_data,
        status_tiket=status,
        nomor_surat_pengantar=nomor_nd,
        tgl_terima_dip=timezone.datetime(2026, 6, 1, 9, 0),
    )
    if user is not None:
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE, active=True)
    return tiket


@pytest.fixture
def wilayah(db, authenticated_user):
    """One Kanwil holding a PV ILAP (direct) and a PD ILAP (through a KPP)."""
    kanwil = KanwilFactory()
    kpp = KPPFactory(id_kanwil=kanwil)

    ilap_pv = ILAPFactory(nama_ilap='PROVINSI CONTOH')
    ILAPKPP.objects.create(id_ilap=ilap_pv, kpp=False, id_kanwil=kanwil)

    ilap_pd = ILAPFactory(nama_ilap='KABUPATEN CONTOH')
    ILAPKPP.objects.create(id_ilap=ilap_pd, kpp=True, id_kpp=kpp)

    ilap_nasional = ILAPFactory(nama_ilap='LEMBAGA NASIONAL')  # no wilayah mapping

    periode_pengiriman = PeriodePengirimanFactory()

    return {
        'kanwil': kanwil,
        'kpp': kpp,
        'pv': ilap_pv,
        'pd': ilap_pd,
        'nasional': ilap_nasional,
        'tiket_pv_nd1': _tiket(ilap_pv, ND_SATU, periode_pengiriman, authenticated_user),
        'tiket_pd_nd1': _tiket(ilap_pd, ND_SATU, periode_pengiriman, authenticated_user),
        'tiket_pv_nd2': _tiket(ilap_pv, ND_DUA, periode_pengiriman, authenticated_user),
        'tiket_nasional': _tiket(ilap_nasional, 'B-700/NAS/06/2026', periode_pengiriman,
                                 authenticated_user),
    }


class TestILAPKPPMapping:
    """The `kpp` flag decides which side of the relation carries the wilayah."""

    def test_pv_ilap_resolves_kanwil_without_kpp(self, wilayah):
        rel = ILAPKPP.objects.get(id_ilap=wilayah['pv'])
        assert rel.kpp is False
        assert rel.id_kpp is None
        assert rel.kanwil == wilayah['kanwil']
        assert wilayah['pv'].kanwil == wilayah['kanwil']

    def test_pd_ilap_resolves_kanwil_through_kpp(self, wilayah):
        rel = ILAPKPP.objects.get(id_ilap=wilayah['pd'])
        assert rel.kpp is True
        assert rel.id_kanwil is None
        assert rel.kanwil == wilayah['kanwil']
        assert wilayah['pd'].kanwil == wilayah['kanwil']

    def test_nasional_ilap_has_no_kanwil(self, wilayah):
        assert wilayah['nasional'].kanwil is None
        assert wilayah['nasional'].kanwil_list == []

    def test_regional_and_nasional_querysets_are_disjoint(self, wilayah):
        regional_ids = set(regional_ilap_queryset().values_list('id', flat=True))
        nasional_ids = set(nasional_ilap_queryset().values_list('id', flat=True))
        assert {wilayah['pv'].pk, wilayah['pd'].pk} <= regional_ids
        assert wilayah['nasional'].pk in nasional_ids
        assert not regional_ids & nasional_ids


class TestScopedTiketQueryset:
    """One Kanwil gathers tikets across every ILAP mapped to it."""

    def test_kanwil_scope_spans_both_mapping_shapes(self, wilayah):
        ids = set(scoped_tiket_queryset(kanwil_id=wilayah['kanwil'].pk).values_list('id', flat=True))
        assert ids == {
            wilayah['tiket_pv_nd1'].pk,
            wilayah['tiket_pd_nd1'].pk,
            wilayah['tiket_pv_nd2'].pk,
        }

    def test_nd_pengantar_narrows_the_scope(self, wilayah):
        ids = set(
            scoped_tiket_queryset(kanwil_id=wilayah['kanwil'].pk, nomor_nd_pengantar=ND_SATU)
            .values_list('id', flat=True)
        )
        assert ids == {wilayah['tiket_pv_nd1'].pk, wilayah['tiket_pd_nd1'].pk}

    def test_nd_options_are_deduplicated_and_sorted(self, wilayah):
        assert nd_pengantar_options(kanwil_id=wilayah['kanwil'].pk) == [ND_SATU, ND_DUA]

    def test_ilap_scope_ignores_other_ilap(self, wilayah):
        ids = set(scoped_tiket_queryset(ilap_id=wilayah['nasional'].pk).values_list('id', flat=True))
        assert ids == {wilayah['tiket_nasional'].pk}

    def test_without_scope_nothing_is_selectable(self, wilayah):
        assert scoped_tiket_queryset().count() == 0


@pytest.mark.django_db
class TestTandaTerimaEndpoints:
    """The AJAX endpoints backing the Tambah form."""

    def test_tikets_endpoint_requires_a_scope(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(reverse('tanda_terima_tikets_by_ilap'))
        assert resp.status_code == 400

    def test_tikets_endpoint_by_kanwil_and_nd(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        resp = client.get(reverse('tanda_terima_tikets_by_ilap'), {
            'kanwil_id': wilayah['kanwil'].pk,
            'nd_pengantar': ND_SATU,
        })
        assert resp.status_code == 200
        rows = resp.json()['data']
        assert {r['nama_ilap'] for r in rows} == {'PROVINSI CONTOH', 'KABUPATEN CONTOH'}
        assert {r['nd_pengantar'] for r in rows} == {ND_SATU}

    def test_nd_options_endpoint(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        resp = client.get(reverse('tanda_terima_nd_pengantar_options'),
                          {'kanwil_id': wilayah['kanwil'].pk})
        assert resp.status_code == 200
        assert resp.json()['data'] == [ND_SATU, ND_DUA]

    def test_nd_options_endpoint_requires_a_scope(self, client, admin_user):
        client.force_login(admin_user)
        assert client.get(reverse('tanda_terima_nd_pengantar_options')).status_code == 400


@pytest.mark.django_db
class TestTandaTerimaCreation:
    """Recording a tanda terima under each scope."""

    def _post(self, client, **extra):
        payload = {
            'tanggal_tanda_terima': '2026-07-20T10:00',
            'nomor_tanda_terima': '90001.TTD/PJ.1031/2026',
            'tahun_terima': '2026',
        }
        payload.update(extra)
        return client.post(reverse('tanda_terima_data_create'), payload,
                           HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_regional_receipt_covers_several_ilap_at_once(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        tiket_ids = [str(wilayah['tiket_pv_nd1'].pk), str(wilayah['tiket_pd_nd1'].pk)]

        resp = self._post(
            client,
            lingkup='regional',
            id_kanwil=str(wilayah['kanwil'].pk),
            nomor_nd_pengantar=ND_SATU,
            tiket_ids=tiket_ids,
        )
        assert resp.status_code == 200 and resp.json().get('success') is True, resp.content

        tanda_terima = TandaTerimaData.objects.get(id_kanwil=wilayah['kanwil'])
        assert tanda_terima.id_ilap is None
        assert tanda_terima.is_regional
        assert tanda_terima.nama_sumber == wilayah['kanwil'].nama_kanwil
        assert tanda_terima.nomor_nd_pengantar == ND_SATU
        assert DetilTandaTerima.objects.filter(id_tanda_terima=tanda_terima).count() == 2
        assert Tiket.objects.filter(id__in=tiket_ids, tanda_terima=True).count() == 2

    def test_recorded_tikets_leave_the_kanwil_scope(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        self._post(
            client,
            lingkup='regional',
            id_kanwil=str(wilayah['kanwil'].pk),
            nomor_nd_pengantar=ND_SATU,
            tiket_ids=[str(wilayah['tiket_pv_nd1'].pk)],
        )
        remaining = set(
            scoped_tiket_queryset(kanwil_id=wilayah['kanwil'].pk).values_list('id', flat=True)
        )
        assert wilayah['tiket_pv_nd1'].pk not in remaining
        assert wilayah['tiket_pd_nd1'].pk in remaining

    def test_nasional_receipt_stays_keyed_on_the_ilap(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        resp = self._post(
            client,
            lingkup='nasional',
            id_ilap=str(wilayah['nasional'].pk),
            tiket_ids=[str(wilayah['tiket_nasional'].pk)],
        )
        assert resp.status_code == 200 and resp.json().get('success') is True, resp.content

        tanda_terima = TandaTerimaData.objects.get(id_ilap=wilayah['nasional'])
        assert tanda_terima.id_kanwil is None
        assert not tanda_terima.is_regional
        assert tanda_terima.nama_sumber == wilayah['nasional'].nama_ilap

    def test_scope_is_inferred_when_lingkup_is_omitted(self, client, admin_user, wilayah):
        """Callers that only know about the ILAP flow keep working."""
        client.force_login(admin_user)
        resp = self._post(
            client,
            id_ilap=str(wilayah['nasional'].pk),
            tiket_ids=[str(wilayah['tiket_nasional'].pk)],
        )
        assert resp.status_code == 200 and resp.json().get('success') is True, resp.content
        assert TandaTerimaData.objects.filter(id_ilap=wilayah['nasional']).exists()

    def test_regional_ilap_cannot_be_used_as_an_ilap_scope(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        resp = self._post(
            client,
            lingkup='nasional',
            id_ilap=str(wilayah['pv'].pk),
            tiket_ids=[str(wilayah['tiket_pv_nd1'].pk)],
        )
        assert resp.status_code == 200
        assert resp.json().get('success') is not True
        assert not TandaTerimaData.objects.filter(id_ilap=wilayah['pv']).exists()

    def test_regional_scope_without_kanwil_is_rejected(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        resp = self._post(
            client,
            lingkup='regional',
            tiket_ids=[str(wilayah['tiket_pv_nd1'].pk)],
        )
        assert resp.status_code == 200
        assert resp.json().get('success') is not True
        assert not TandaTerimaData.objects.filter(id_kanwil=wilayah['kanwil']).exists()


@pytest.mark.django_db
class TestTandaTerimaListing:
    """The DataTables payload reports the recorded scope."""

    def test_row_reports_kanwil_and_nd_pengantar(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        client.post(
            reverse('tanda_terima_data_create'),
            {
                'lingkup': 'regional',
                'id_kanwil': str(wilayah['kanwil'].pk),
                'nomor_nd_pengantar': ND_SATU,
                'tanggal_tanda_terima': '2026-07-20T10:00',
                'nomor_tanda_terima': '90001.TTD/PJ.1031/2026',
                'tahun_terima': '2026',
                'tiket_ids': [str(wilayah['tiket_pv_nd1'].pk)],
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        resp = client.get(reverse('tanda_terima_data_data'),
                          {'draw': 1, 'start': 0, 'length': 25})
        assert resp.status_code == 200
        tanda_terima = TandaTerimaData.objects.get(id_kanwil=wilayah['kanwil'])
        row = next(r for r in resp.json()['data'] if r['id'] == tanda_terima.pk)
        assert row['sumber'] == wilayah['kanwil'].nama_kanwil
        assert row['lingkup'] == 'Regional'
        # The ND Pengantar is still recorded, it is just not a list column.
        assert tanda_terima.nomor_nd_pengantar == ND_SATU


@pytest.mark.django_db
class TestDocumentGeneration:
    """A Kanwil-scoped receipt is issued in the name of that Kanwil."""

    def test_diterima_dari_uses_the_recorded_kanwil(self, client, admin_user, wilayah):
        from django.test import RequestFactory

        from diamond_web.views.tiket.documents import _generate_single_document

        client.force_login(admin_user)
        client.post(
            reverse('tanda_terima_data_create'),
            {
                'lingkup': 'regional',
                'id_kanwil': str(wilayah['kanwil'].pk),
                'nomor_nd_pengantar': ND_SATU,
                'tanggal_tanda_terima': '2026-07-20T10:00',
                'nomor_tanda_terima': '90001.TTD/PJ.1031/2026',
                'tahun_terima': '2026',
                'tiket_ids': [str(wilayah['tiket_pv_nd1'].pk)],
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        request = RequestFactory().get('/')
        request.user = admin_user
        doc, _ = _generate_single_document(request, wilayah['tiket_pv_nd1'].pk, 'tanda_terima_only')
        text = '\n'.join(p.text for p in doc.paragraphs)
        text += '\n'.join(c.text for t in doc.tables for r in t.rows for c in r.cells)
        assert wilayah['kanwil'].nama_kanwil in text


@pytest.mark.django_db
class TestTidakDiterbitkan:
    """Marking tikets as processed without issuing a Tanda Terima."""

    def test_marks_tiket_without_creating_a_receipt(self, client, authenticated_user, wilayah):
        from diamond_web.constants.tiket_action_types import TandaTerimaActionType
        from diamond_web.models import TiketAction

        client.force_login(authenticated_user)
        tiket = wilayah['tiket_pv_nd1']
        resp = client.post(reverse('tidak_terbit_tanda_terima', args=[tiket.pk]),
                           HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert resp.status_code == 200 and resp.json()['success'] is True, resp.content

        tiket.refresh_from_db()
        assert tiket.tanda_terima is True
        assert not DetilTandaTerima.objects.filter(id_tiket=tiket).exists()
        assert TiketAction.objects.filter(
            id_tiket=tiket, action=TandaTerimaActionType.TIDAK_DITERBITKAN
        ).exists()

    def test_marked_tiket_leaves_the_selectable_list(self, client, authenticated_user, wilayah):
        """It is flagged without a DetilTandaTerima row, so the flag must be honoured.

        Otherwise it stays listed and marking it again fails with
        "Tiket ini sudah memiliki Tanda Terima".
        """
        client.force_login(authenticated_user)
        tiket = wilayah['tiket_pv_nd1']
        client.post(reverse('tidak_terbit_tanda_terima', args=[tiket.pk]),
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        assert not DetilTandaTerima.objects.filter(id_tiket=tiket).exists()
        remaining = set(
            scoped_tiket_queryset(kanwil_id=wilayah['kanwil'].pk).values_list('id', flat=True)
        )
        assert tiket.pk not in remaining
        assert wilayah['tiket_pd_nd1'].pk in remaining

        resp = client.get(reverse('tanda_terima_tikets_by_ilap'),
                          {'kanwil_id': wilayah['kanwil'].pk, 'nd_pengantar': ND_SATU})
        assert tiket.pk not in {r['id'] for r in resp.json()['data']}

    def test_marked_tiket_leaves_the_nasional_list_too(self, client, authenticated_user, wilayah):
        client.force_login(authenticated_user)
        tiket = wilayah['tiket_nasional']
        client.post(reverse('tidak_terbit_tanda_terima', args=[tiket.pk]),
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        resp = client.get(reverse('tanda_terima_tikets_by_ilap'),
                          {'ilap_id': wilayah['nasional'].pk})
        assert resp.json()['data'] == []

    def test_rejects_a_tiket_that_already_has_a_receipt(self, client, authenticated_user, wilayah):
        client.force_login(authenticated_user)
        tiket = wilayah['tiket_pv_nd1']
        tiket.tanda_terima = True
        tiket.save(update_fields=['tanda_terima'])

        resp = client.post(reverse('tidak_terbit_tanda_terima', args=[tiket.pk]),
                           HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert resp.status_code == 400
        assert resp.json()['success'] is False

    def test_denied_for_a_non_pic_user(self, client, pide_user, wilayah):
        client.force_login(pide_user)
        resp = client.post(reverse('tidak_terbit_tanda_terima', args=[wilayah['tiket_pv_nd1'].pk]),
                           HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert resp.status_code in (302, 403)

    def test_create_form_offers_the_button_but_the_edit_form_does_not(self, client, admin_user, wilayah):
        client.force_login(admin_user)

        resp = client.get(reverse('tanda_terima_data_create'), {'ajax': '1'})
        assert 'tidak-terbit-tt-btn' in resp.json()['html']

        client.post(
            reverse('tanda_terima_data_create'),
            {
                'lingkup': 'regional',
                'id_kanwil': str(wilayah['kanwil'].pk),
                'nomor_nd_pengantar': ND_SATU,
                'tanggal_tanda_terima': '2026-07-20T10:00',
                'nomor_tanda_terima': '90001.TTD/PJ.1031/2026',
                'tahun_terima': '2026',
                'tiket_ids': [str(wilayah['tiket_pv_nd1'].pk)],
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        tanda_terima = TandaTerimaData.objects.get(id_kanwil=wilayah['kanwil'])
        TiketPIC.objects.filter(id_tiket=wilayah['tiket_pv_nd1']).update(id_user=admin_user)

        resp = client.get(reverse('tanda_terima_data_update', args=[tanda_terima.pk]),
                          {'ajax': '1'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert 'tidak-terbit-tt-btn' not in resp.json()['html']


@pytest.mark.django_db
class TestListColumns:
    """The list payload no longer carries the Jenis Data column."""

    def test_jenis_data_and_nd_pengantar_are_not_reported(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        resp = client.get(reverse('tanda_terima_data_data'), {'draw': 1, 'start': 0, 'length': 5})
        assert resp.status_code == 200
        rows = resp.json()['data']
        assert rows
        assert 'jenis_data' not in rows[0]
        assert 'nomor_nd_pengantar' not in rows[0]
        assert {'sumber', 'lingkup', 'id_perekam', 'status'} <= set(rows[0])

    def test_row_actions_offer_only_the_tanda_terima_download(self, client, admin_user, wilayah):
        """The separate Register download was dropped from this list."""
        client.force_login(admin_user)
        client.post(
            reverse('tanda_terima_data_create'),
            {
                'lingkup': 'regional',
                'id_kanwil': str(wilayah['kanwil'].pk),
                'nomor_nd_pengantar': ND_SATU,
                'tanggal_tanda_terima': '2026-07-20T10:00',
                'nomor_tanda_terima': '',
                'tahun_terima': '2026',
                'tiket_ids': [str(wilayah['tiket_pv_nd1'].pk)],
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        tanda_terima = TandaTerimaData.objects.get(id_kanwil=wilayah['kanwil'])

        resp = client.get(reverse('tanda_terima_data_data'),
                          {'draw': 1, 'start': 0, 'length': 25})
        row = next(r for r in resp.json()['data'] if r['id'] == tanda_terima.pk)
        assert "'tanda_terima'" in row['actions']
        assert "'register'" not in row['actions']

    def test_column_search_indexes_shifted(self, client, admin_user, wilayah):
        """Columns are: nomor, tanggal, Kanwil/ILAP, perekam, status."""
        client.force_login(admin_user)
        resp = client.get(reverse('tanda_terima_data_data'), {
            'draw': 1, 'start': 0, 'length': 25,
            'columns_search[]': ['', '', '', 'no-such-user', ''],
        })
        assert resp.status_code == 200
        assert resp.json()['data'] == []

    def test_column_search_matches_the_recorded_kanwil(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        client.post(
            reverse('tanda_terima_data_create'),
            {
                'lingkup': 'regional',
                'id_kanwil': str(wilayah['kanwil'].pk),
                'nomor_nd_pengantar': ND_SATU,
                'tanggal_tanda_terima': '2026-07-20T10:00',
                'nomor_tanda_terima': '90001.TTD/PJ.1031/2026',
                'tahun_terima': '2026',
                'tiket_ids': [str(wilayah['tiket_pv_nd1'].pk)],
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        resp = client.get(reverse('tanda_terima_data_data'), {
            'draw': 1, 'start': 0, 'length': 25,
            'columns_search[]': ['', '', wilayah['kanwil'].nama_kanwil, '', ''],
        })
        assert resp.status_code == 200
        rows = resp.json()['data']
        assert rows and all(r['sumber'] == wilayah['kanwil'].nama_kanwil for r in rows)


@pytest.mark.django_db
class TestCancellationFreesTikets:
    """Cancelling a receipt resets `tanda_terima`, returning tikets to the pool."""

    def test_cancelled_receipt_returns_its_tikets(self, client, authenticated_user, wilayah):
        client.force_login(authenticated_user)
        tiket = wilayah['tiket_pv_nd1']

        client.post(
            reverse('tanda_terima_data_create'),
            {
                'lingkup': 'regional',
                'id_kanwil': str(wilayah['kanwil'].pk),
                'nomor_nd_pengantar': ND_SATU,
                'tanggal_tanda_terima': '2026-07-20T10:00',
                'nomor_tanda_terima': '90001.TTD/PJ.1031/2026',
                'tahun_terima': '2026',
                'tiket_ids': [str(tiket.pk)],
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        tanda_terima = TandaTerimaData.objects.get(id_kanwil=wilayah['kanwil'])
        assert tiket.pk not in set(
            scoped_tiket_queryset(kanwil_id=wilayah['kanwil'].pk).values_list('id', flat=True)
        )

        client.post(reverse('tanda_terima_data_delete', args=[tanda_terima.pk]),
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        tiket.refresh_from_db()
        assert tiket.tanda_terima is False
        assert tiket.pk in set(
            scoped_tiket_queryset(kanwil_id=wilayah['kanwil'].pk).values_list('id', flat=True)
        )


@pytest.mark.django_db
class TestNomorAllocation:
    """`nomor_tanda_terima` is allocated server-side, not trusted from the post.

    The field is rendered read-only but still round-trips through the
    browser, so by the time it arrives it may name a number someone else has
    taken, or one from a different year's series. `(nomor, tahun)` is unique,
    so getting this wrong means an IntegrityError instead of a saved record.
    """

    def _post(self, client, nomor, tanggal, ilap, tiket):
        return client.post(
            reverse('tanda_terima_data_create'),
            {
                'lingkup': 'nasional',
                'id_ilap': str(ilap.pk),
                'tanggal_tanda_terima': tanggal,
                'nomor_tanda_terima': nomor,
                'tahun_terima': tanggal[:4],
                'tiket_ids': [str(tiket.pk)],
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_a_taken_nomor_is_reallocated_instead_of_erroring(self, client, admin_user, wilayah):
        from diamond_web.utils.tanda_terima_nomor import next_nomor_tanda_terima

        client.force_login(admin_user)
        stale = next_nomor_tanda_terima(2026)
        nomor = f'{str(stale).zfill(5)}.TTD/PJ.1031/2026'

        first = self._post(client, nomor, '2026-07-20', wilayah['nasional'],
                           wilayah['tiket_nasional'])
        assert first.json()['success'] is True

        # A second user still had the same number on screen.
        other = _tiket(wilayah['nasional'], 'B-701/NAS/06/2026',
                       wilayah['tiket_nasional'].id_periode_data.id_periode_pengiriman)
        second = self._post(client, nomor, '2026-07-20', wilayah['nasional'], other)
        assert second.json()['success'] is True

        nomors = sorted(TandaTerimaData.objects.filter(
            tahun_terima=2026, nomor_tanda_terima__gte=stale
        ).values_list('nomor_tanda_terima', flat=True))
        assert nomors[:2] == [stale, stale + 1]

    def test_year_always_follows_the_date(self, client, admin_user, wilayah):
        """A nomor from another year's series must not be carried over."""
        client.force_login(admin_user)
        tiket = _tiket(wilayah['nasional'], 'B-702/NAS/06/2025',
                       wilayah['tiket_nasional'].id_periode_data.id_periode_pengiriman)
        tiket.tgl_terima_dip = timezone.datetime(2025, 1, 1, 9, 0)
        tiket.save(update_fields=['tgl_terima_dip'])

        resp = self._post(client, '09999.TTD/PJ.1031/2026', '2025-06-01',
                          wilayah['nasional'], tiket)
        assert resp.json()['success'] is True

        created = TandaTerimaData.objects.filter(tahun_terima=2025).order_by('-id').first()
        assert created.tahun_terima == 2025
        assert created.nomor_tanda_terima != 9999

    def test_a_concurrent_insert_is_retried(self, client, admin_user, wilayah, monkeypatch):
        from diamond_web.forms import tanda_terima_data as form_mod
        from diamond_web.utils import tanda_terima_nomor as nomor_mod

        real_allocate = nomor_mod.allocate_nomor_tanda_terima
        calls = {'n': 0}

        def racing_allocate(tahun, preferred=None, exclude_pk=None):
            nomor = real_allocate(tahun, preferred=preferred, exclude_pk=exclude_pk)
            calls['n'] += 1
            if calls['n'] == 1:
                # Another request commits this exact number first.
                TandaTerimaData.objects.create(
                    nomor_tanda_terima=nomor, tahun_terima=tahun,
                    tanggal_tanda_terima=timezone.datetime(tahun, 7, 1, 9, 0),
                    id_ilap=wilayah['nasional'], id_perekam=admin_user,
                )
            return nomor

        monkeypatch.setattr(form_mod, 'allocate_nomor_tanda_terima', racing_allocate)
        client.force_login(admin_user)
        resp = self._post(client, '', '2026-07-20', wilayah['nasional'],
                          wilayah['tiket_nasional'])
        assert resp.status_code == 200
        assert resp.json()['success'] is True
        assert calls['n'] == 2, 'expected exactly one retry'


@pytest.mark.django_db
class TestTanggalValidation:
    """Date rules hold on the tiket detail page too, not just the list page."""

    def _post_from_tiket(self, client, tiket, tanggal):
        return client.post(
            reverse('tanda_terima_data_from_tiket_create', args=[tiket.pk]),
            {
                'tanggal_tanda_terima': tanggal,
                'nomor_tanda_terima': '',
                'tahun_terima': tanggal[:4],
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_rejects_a_date_before_tanggal_terima_dip(self, client, authenticated_user, wilayah):
        client.force_login(authenticated_user)
        tiket = wilayah['tiket_pv_nd1']  # tgl_terima_dip = 2026-06-01
        resp = self._post_from_tiket(client, tiket, '2026-05-01')
        assert resp.json()['success'] is False
        assert not DetilTandaTerima.objects.filter(id_tiket=tiket).exists()

    def test_rejects_a_future_date(self, client, authenticated_user, wilayah):
        client.force_login(authenticated_user)
        tiket = wilayah['tiket_pv_nd1']
        resp = self._post_from_tiket(client, tiket, '2099-01-01')
        assert resp.json()['success'] is False
        assert not DetilTandaTerima.objects.filter(id_tiket=tiket).exists()

    def test_accepts_a_date_on_or_after_tanggal_terima_dip(self, client, authenticated_user, wilayah):
        client.force_login(authenticated_user)
        tiket = wilayah['tiket_pv_nd1']
        resp = self._post_from_tiket(client, tiket, '2026-06-15')
        assert resp.json()['success'] is True, resp.content
        assert DetilTandaTerima.objects.filter(id_tiket=tiket).exists()

    def test_the_same_rule_applies_on_the_list_page(self, client, admin_user, wilayah):
        client.force_login(admin_user)
        resp = client.post(
            reverse('tanda_terima_data_create'),
            {
                'lingkup': 'regional',
                'id_kanwil': str(wilayah['kanwil'].pk),
                'tanggal_tanda_terima': '2026-05-01',  # before tgl_terima_dip
                'nomor_tanda_terima': '',
                'tahun_terima': '2026',
                'tiket_ids': [str(wilayah['tiket_pv_nd1'].pk)],
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.json()['success'] is False
        assert not TandaTerimaData.objects.filter(id_kanwil=wilayah['kanwil']).exists()
