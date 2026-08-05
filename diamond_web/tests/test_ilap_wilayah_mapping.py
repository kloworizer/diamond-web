"""Tests for the KPP / Kanwil mapping of the ILAP CRUD.

A Regional ILAP of kategori PD (Pemerintah Daerah Kabupaten/Kota) is mapped to
a KPP, while one of kategori PV (Pemerintah Daerah Provinsi) has no KPP
counterpart and is mapped straight to a Kanwil. Both live in the same
``ILAPKPP`` table, told apart by the ``kpp`` flag.
"""
import pytest

from diamond_web.forms.ilap import ILAPForm
from diamond_web.models.ilap_kpp import ILAPKPP
from diamond_web.models.kategori_ilap import KategoriILAP
from diamond_web.models.kategori_wilayah import KategoriWilayah


# The seed migrations already ship these reference rows, so reuse them instead
# of creating duplicates that would trip their unique constraints.
@pytest.fixture
def kategori_pd(db):
    obj, _ = KategoriILAP.objects.get_or_create(
        id_kategori='PD', defaults={'nama_kategori': 'PEMERINTAH DAERAH KABUPATEN/KOTA'}
    )
    return obj


@pytest.fixture
def kategori_pv(db):
    obj, _ = KategoriILAP.objects.get_or_create(
        id_kategori='PV', defaults={'nama_kategori': 'PEMERINTAH DAERAH PROVINSI'}
    )
    return obj


@pytest.fixture
def wilayah_regional(db):
    obj, _ = KategoriWilayah.objects.get_or_create(deskripsi='Regional')
    return obj


@pytest.fixture
def wilayah_nasional(db):
    obj, _ = KategoriWilayah.objects.get_or_create(deskripsi='Nasional')
    return obj


def form_data(kategori, wilayah, **extra):
    """Build a minimal valid ILAPForm payload."""
    data = {
        'id_kategori': kategori.id_kategori,
        'id_ilap': f'{kategori.id_kategori}001',
        'nama_ilap': f'ILAP {kategori.id_kategori}',
        'id_kategori_wilayah': wilayah.pk,
    }
    data.update(extra)
    return data


@pytest.mark.django_db
class TestILAPFormWilayahMapping:
    """Saving an ILAP writes the mapping row that matches its kategori."""

    def test_pv_regional_saves_kanwil_relation(self, kategori_pv, wilayah_regional, kanwil):
        form = ILAPForm(data=form_data(
            kategori_pv, wilayah_regional, kanwil_list=[kanwil.pk]
        ))
        assert form.is_valid(), form.errors
        ilap = form.save()

        relations = list(ILAPKPP.objects.filter(id_ilap=ilap))
        assert len(relations) == 1
        assert relations[0].kpp is False
        assert relations[0].id_kanwil_id == kanwil.pk
        assert relations[0].id_kpp_id is None

    def test_pd_regional_saves_kpp_relation(self, kategori_pd, wilayah_regional, kpp):
        form = ILAPForm(data=form_data(
            kategori_pd, wilayah_regional, kpp_list=[kpp.pk]
        ))
        assert form.is_valid(), form.errors
        ilap = form.save()

        relations = list(ILAPKPP.objects.filter(id_ilap=ilap))
        assert len(relations) == 1
        assert relations[0].kpp is True
        assert relations[0].id_kpp_id == kpp.pk
        assert relations[0].id_kanwil_id is None

    def test_pv_ignores_kpp_selection(self, kategori_pv, wilayah_regional, kpp, kanwil):
        """A PV ILAP has no KPP counterpart, so a posted kpp_list is dropped."""
        form = ILAPForm(data=form_data(
            kategori_pv, wilayah_regional, kpp_list=[kpp.pk], kanwil_list=[kanwil.pk]
        ))
        assert form.is_valid(), form.errors
        ilap = form.save()

        relations = list(ILAPKPP.objects.filter(id_ilap=ilap))
        assert len(relations) == 1
        assert relations[0].id_kanwil_id == kanwil.pk

    def test_pd_ignores_kanwil_selection(self, kategori_pd, wilayah_regional, kpp, kanwil):
        form = ILAPForm(data=form_data(
            kategori_pd, wilayah_regional, kpp_list=[kpp.pk], kanwil_list=[kanwil.pk]
        ))
        assert form.is_valid(), form.errors
        ilap = form.save()

        relations = list(ILAPKPP.objects.filter(id_ilap=ilap))
        assert len(relations) == 1
        assert relations[0].id_kpp_id == kpp.pk

    def test_non_regional_drops_every_selection(self, kategori_pv, wilayah_nasional, kanwil):
        form = ILAPForm(data=form_data(
            kategori_pv, wilayah_nasional, kanwil_list=[kanwil.pk]
        ))
        assert form.is_valid(), form.errors
        ilap = form.save()

        assert ILAPKPP.objects.filter(id_ilap=ilap).count() == 0


@pytest.mark.django_db
class TestILAPFormWilayahEdit:
    """Editing an existing ILAP round-trips its mapping rows."""

    def _create_pv(self, kategori_pv, wilayah_regional, kanwil):
        form = ILAPForm(data=form_data(
            kategori_pv, wilayah_regional, kanwil_list=[kanwil.pk]
        ))
        assert form.is_valid(), form.errors
        return form.save()

    def test_edit_prepopulates_kanwil_list(self, kategori_pv, wilayah_regional, kanwil):
        ilap = self._create_pv(kategori_pv, wilayah_regional, kanwil)

        form = ILAPForm(instance=ilap)
        assert list(form.initial['kanwil_list']) == [kanwil.pk]
        assert list(form.initial['kpp_list']) == []

    def test_edit_replaces_kanwil_selection(self, kategori_pv, wilayah_regional, kanwil,
                                            django_user_model):
        from diamond_web.tests.conftest import KanwilFactory

        ilap = self._create_pv(kategori_pv, wilayah_regional, kanwil)
        other_kanwil = KanwilFactory()

        form = ILAPForm(
            data=form_data(kategori_pv, wilayah_regional,
                           nama_ilap=ilap.nama_ilap, kanwil_list=[other_kanwil.pk]),
            instance=ilap,
        )
        assert form.is_valid(), form.errors
        form.save()

        relations = list(ILAPKPP.objects.filter(id_ilap=ilap))
        assert len(relations) == 1
        assert relations[0].id_kanwil_id == other_kanwil.pk

    def test_edit_to_non_regional_clears_relations(self, kategori_pv, wilayah_regional,
                                                   wilayah_nasional, kanwil):
        ilap = self._create_pv(kategori_pv, wilayah_regional, kanwil)

        form = ILAPForm(
            data=form_data(kategori_pv, wilayah_nasional, nama_ilap=ilap.nama_ilap),
            instance=ilap,
        )
        assert form.is_valid(), form.errors
        form.save()

        assert ILAPKPP.objects.filter(id_ilap=ilap).count() == 0


@pytest.mark.django_db
class TestILAPDataWilayahColumn:
    """The DataTables endpoint shows the Kanwil name for ILAP without a KPP."""

    def test_pv_row_shows_kanwil_name(self, client, p3de_admin_user, kategori_pv,
                                      wilayah_regional, kanwil):
        import json
        from django.urls import reverse
        from diamond_web.models.ilap import ILAP

        ilap = ILAP.objects.create(
            id_ilap='PV900', id_kategori=kategori_pv, nama_ilap='PROVINSI TEST',
            id_kategori_wilayah=wilayah_regional,
        )
        ILAPKPP.objects.create(id_ilap=ilap, kpp=False, id_kanwil=kanwil)

        client.force_login(p3de_admin_user)
        resp = client.get(reverse('ilap_data'), {
            'draw': 1, 'start': 0, 'length': 10, 'columns_search[]': 'PV900',
        })
        assert resp.status_code == 200
        rows = json.loads(resp.content)['data']
        assert len(rows) == 1
        assert rows[0]['id_kpp'] == kanwil.nama_kanwil
