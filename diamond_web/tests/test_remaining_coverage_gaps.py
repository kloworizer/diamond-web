"""Additional coverage tests for the remaining report, bulk, form, and model gaps."""

import json
from datetime import date, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.db.models import Max
from django.urls import reverse

from diamond_web.forms.laporan_metrik_data_eksternal import (
    LaporanMetrikDataEksternalExportResource,
    LaporanMetrikDataEksternalFilterForm,
)
from diamond_web.forms.laporan_sla_identifikasi import (
    LaporanSLAIdentifikasiExportResource,
    LaporanSLAIdentifikasiFilterForm,
)
from diamond_web.forms.laporan_sla_perekaman import (
    LaporanSLAPerekamanExportResource,
    LaporanSLAPerekamanFilterForm,
)
from diamond_web.forms.laporan_transfer import (
    LaporanTransferExportResource,
    LaporanTransferFilterForm,
)
from diamond_web.forms.rekam_hasil_penelitian import RekamHasilPenelitianForm
from diamond_web.models import (
    BentukData,
    CaraPenyampaian,
    DasarHukum,
    DetilTandaTerima,
    ILAP,
    JenisDataILAP,
    JenisTabel,
    KategoriILAP,
    KategoriWilayah,
    KlasifikasiJenisData,
    KPP,
    PIC,
    PeriodeJenisData,
    PeriodePengiriman,
    StatusData,
    StatusPenelitian,
    TandaTerimaData,
    Tiket,
)
from diamond_web.tests.conftest import (
    BentukDataFactory,
    CaraPenyampaianFactory,
    ILAPFactory,
    JenisDataILAPFactory,
    JenisTabelFactory,
    KategoriILAPFactory,
    KategoriWilayahFactory,
    KanwilFactory,
    KPPFactory,
    PeriodeJenisDataFactory,
    PeriodePengirimanFactory,
    StatusDataFactory,
    StatusPenelitianFactory,
    TiketFactory,
    UserFactory,
)
from diamond_web.views.bulk_document_generation import (
    _apply_doc_type_filter,
    _base_queryset,
    _build_table_doc,
    _format_date_indonesian,
    _format_periode_tiket,
    _generate_docx_for_tickets,
    _is_p3de_user,
    _parse_date,
)
from diamond_web.views.laporan_metrik_data_eksternal import (
    laporan_metrik_data_eksternal_data,
    laporan_metrik_data_eksternal_export,
)
from diamond_web.views.laporan_pide_filter_options import laporan_pide_filter_options
from diamond_web.views.laporan_register_penerimaan import (
    register_penerimaan_data,
    register_penerimaan_export,
)
from diamond_web.views.laporan_sla_identifikasi import (
    laporan_sla_identifikasi_data,
    laporan_sla_identifikasi_export,
)
from diamond_web.views.laporan_sla_perekaman import (
    laporan_sla_perekaman_data,
    laporan_sla_perekaman_export,
)
from diamond_web.views.laporan_transfer import (
    laporan_transfer_data,
    laporan_transfer_export,
)
from diamond_web.views.mixins import get_active_p3de_ilap_ids
from diamond_web.views.tiket.documents import _safe_filename_part


def _make_bundle(regional=True):
    kategori_ilap = KategoriILAPFactory()
    kategori_wilayah = KategoriWilayahFactory()
    kanwil = KanwilFactory()
    kpp = KPPFactory(id_kanwil=kanwil)
    ilap = ILAPFactory(id_kategori=kategori_ilap, id_kategori_wilayah=kategori_wilayah)
    from diamond_web.models import ILAPKPP
    ILAPKPP.objects.create(id_ilap=ilap, id_kpp=kpp)
    jenis_tabel = JenisTabelFactory()
    status_data = StatusDataFactory()
    jenis_data = JenisDataILAPFactory(id_ilap=ilap, id_jenis_tabel=jenis_tabel, id_status_data=status_data)
    periode_pengiriman = PeriodePengirimanFactory(periode_penerimaan='Bulanan')
    periode_data = PeriodeJenisDataFactory(
        id_sub_jenis_data_ilap=jenis_data,
        id_periode_pengiriman=periode_pengiriman,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    from diamond_web.models.status_penelitian import StatusPenelitian
    status_penelitian, _ = StatusPenelitian.objects.get_or_create(deskripsi='Lengkap')
    bentuk_data = BentukDataFactory()
    cara_penyampaian = CaraPenyampaianFactory()
    tiket = TiketFactory(
        nomor_tiket='TK-REPORT-001',
        status_tiket=1,
        id_periode_data=periode_data,
        periode=1,
        tahun=2024,
        nomor_surat_pengantar='SP-001',
        tanggal_surat_pengantar=datetime(2024, 1, 10, 9, 0),
        nama_pengirim='Pengirim A',
        id_bentuk_data=bentuk_data,
        id_cara_penyampaian=cara_penyampaian,
        baris_diterima=100,
        baris_lengkap=70,
        baris_tidak_lengkap=30,
        baris_i=40,
        baris_u=25,
        baris_res=15,
        qc_c=5,
        tgl_terima_dip=datetime(2024, 1, 11, 8, 0),
        tgl_transfer=datetime(2024, 1, 12, 10, 0),
        tgl_kirim_pide=datetime(2024, 1, 13, 10, 0),
        tgl_rekam_pide=datetime(2024, 1, 14, 10, 0),
        tanda_terima=True,
        id_status_penelitian=status_penelitian,
    )
    tahun = 2099
    max_nomor = TandaTerimaData.objects.filter(tahun_terima=tahun).aggregate(m=Max('nomor_tanda_terima'))['m'] or 0
    tanda_terima = TandaTerimaData.objects.create(
        nomor_tanda_terima=max_nomor + 1,
        tahun_terima=tahun,
        tanggal_tanda_terima=datetime(2024, 1, 12, 12, 0),
        id_ilap=ilap,
        id_perekam=UserFactory(),
        active=True,
    )
    DetilTandaTerima.objects.create(id_tanda_terima=tanda_terima, id_tiket=tiket)
    KlasifikasiJenisData.objects.create(
        id_sub_jenis_data=jenis_data,
        id_klasifikasi_tabel=DasarHukum.objects.create(deskripsi='Dasar Hukum A'),
    )
    return {
        'tiket': tiket,
        'ilap': ilap,
        'jenis_data': jenis_data,
        'periode_data': periode_data,
        'tanda_terima': tanda_terima,
    }


def _make_p3de_user(username='p3de_user'):
    user = UserFactory(username=username)
    group, _ = Group.objects.get_or_create(name='user_p3de')
    user.groups.add(group)
    return user


def _make_pide_user(username='pide_user'):
    user = UserFactory(username=username)
    group, _ = Group.objects.get_or_create(name='user_pide')
    user.groups.add(group)
    return user


@pytest.mark.django_db
class TestRemainingFormCoverage:
    def test_filter_forms_and_export_resources(self):
        LaporanMetrikDataEksternalFilterForm()
        LaporanSLAIdentifikasiFilterForm()
        LaporanSLAPerekamanFilterForm()
        LaporanTransferFilterForm()

        assert _safe_filename_part('Report A/B') == 'Report_A_B'
        assert _safe_filename_part('') == 'file'

        tiket = TiketFactory(baris_diterima=10, baris_i=4, baris_u=2, baris_res=1)
        transfer = LaporanTransferExportResource()
        assert transfer.dehydrate_jumlah_data_masuk(tiket) == 10
        assert transfer.dehydrate_jumlah_data_tidak_teridentifikasi(tiket) == 2
        assert transfer.dehydrate_persentase(tiket) == '40.00%'
        assert transfer.dehydrate_keterangan(tiket) == ''

        perekaman = LaporanSLAPerekamanExportResource()
        identifikasi = LaporanSLAIdentifikasiExportResource()
        assert perekaman.dehydrate_sla_perekaman(tiket) == ''
        assert identifikasi.dehydrate_sla_identifikasi(tiket) == ''

        metrik = LaporanMetrikDataEksternalExportResource()
        assert metrik.dehydrate_jumlah_data_masuk(tiket) == 10
        assert metrik.dehydrate_jumlah_data_tidak_teridentifikasi(tiket) == 2
        assert metrik.dehydrate_jumlah_data_res(tiket) == 1
        assert metrik.dehydrate_persentase(tiket) == '40.00%'

    def test_rekam_hasil_penelitian_form_cleaning(self):
        bundle = _make_bundle()
        tiket = bundle['tiket']

        form = RekamHasilPenelitianForm(instance=tiket)
        assert form.fields['catatan'].initial == 'Hasil penelitian direkam'

        from django.utils import timezone
        tiket.tgl_teliti = timezone.now()
        form_update = RekamHasilPenelitianForm(instance=tiket)
        assert form_update.fields['catatan'].initial == 'Hasil penelitian diubah'

        invalid = RekamHasilPenelitianForm(
            data={
                'tgl_teliti': '2024-01-10T10:00',
                'baris_lengkap': 60,
                'baris_tidak_lengkap': 20,
                'catatan': 'Catatan',
            },
            instance=tiket,
        )
        assert not invalid.is_valid()

    def test_model_and_mixin_helpers(self):
        bundle = _make_bundle()
        tanda_terima = bundle['tanda_terima']
        tiket = bundle['tiket']

        assert str(tanda_terima)
        assert tanda_terima.nomor_tanda_terima_format.endswith('/2099')
        assert tanda_terima.nama_ILAP == bundle['ilap'].nama_ilap
        assert tanda_terima.daftar_jenis_data
        assert tanda_terima.periode_data == 'Bulanan'
        assert str(DetilTandaTerima.objects.get(id_tiket=tiket))

        active_user = _make_p3de_user('active-helper')
        PIC.objects.create(
            id_sub_jenis_data_ilap=bundle['jenis_data'],
            tipe=PIC.TipePIC.P3DE,
            id_user=active_user,
            start_date=date(2023, 1, 1),
            end_date=None,
        )
        assert get_active_p3de_ilap_ids(active_user)
        assert get_active_p3de_ilap_ids(None) == []


@pytest.mark.django_db
class TestRemainingViewCoverage:
    def test_register_sla_transfer_and_metrik_views(self, client):
        bundle = _make_bundle()
        user = UserFactory(is_superuser=True)
        client.force_login(user)

        assert client.get(reverse('register_penerimaan_data')).status_code == 200
        assert client.get(reverse('laporan_sla_perekaman')).status_code == 200
        assert client.get(reverse('laporan_sla_identifikasi')).status_code == 200
        assert client.get(reverse('laporan_transfer')).status_code == 200
        assert client.get(reverse('laporan_metrik_data_eksternal')).status_code == 200

        register_data = client.get(reverse('register_penerimaan_data_data'), {'bulan': '1', 'tahun': '2024', 'draw': '1', 'start': '0', 'length': '10'})
        assert register_data.status_code == 200
        assert json.loads(register_data.content)['recordsFiltered'] >= 1

        perekaman_data = client.get(reverse('laporan_sla_perekaman_data'), {'draw': '1', 'start': '0', 'length': '10'})
        identifikasi_data = client.get(reverse('laporan_sla_identifikasi_data'), {'draw': '1', 'start': '0', 'length': '10'})
        transfer_data = client.get(reverse('laporan_transfer_data'), {'draw': '1', 'start': '0', 'length': '10'})
        metrik_data = client.get(reverse('laporan_metrik_data_eksternal_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert perekaman_data.status_code == 200
        assert identifikasi_data.status_code == 200
        assert transfer_data.status_code == 200
        assert metrik_data.status_code == 200

        assert client.get(reverse('register_penerimaan_export'), {'bulan': '1', 'tahun': '2024'}).status_code == 200
        assert client.get(reverse('laporan_sla_perekaman_export'), {'tgl_mulai': '2024-01-01T00:00', 'tgl_akhir': '2024-01-31T23:59'}).status_code == 200
        assert client.get(reverse('laporan_sla_identifikasi_export'), {'tgl_mulai': '2024-01-01T00:00', 'tgl_akhir': '2024-01-31T23:59'}).status_code == 200
        assert client.get(reverse('laporan_transfer_export'), {'tgl_mulai': '2024-01-01T00:00', 'tgl_akhir': '2024-01-31T23:59'}).status_code == 200
        assert client.get(reverse('laporan_metrik_data_eksternal_export'), {'tgl_mulai': '2024-01-01T00:00', 'tgl_akhir': '2024-01-31T23:59'}).status_code == 200
        assert client.get(reverse('register_penerimaan_export'), {'bulan': '13', 'tahun': '2024'}).status_code == 400

    def test_pide_filter_options_and_monitoring(self, client):
        bundle = _make_bundle()
        user = _make_pide_user('pide-filter')
        client.force_login(user)

        resp = client.get(reverse('laporan_pide_filter_options'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'ilaps' in data

        resp = client.get(reverse('laporan_pide_filter_options'), {'id_ilap': str(bundle['ilap'].pk)})
        assert resp.status_code == 200

        from diamond_web.views.monitoring_penyampaian_data import get_periods_for_range

        periods = get_periods_for_range(date(2024, 1, 1), date(2024, 1, 3), 'unknown')
        assert len(periods) == 3

        p3de_user = _make_p3de_user('monitor-p3de')
        PIC.objects.create(id_sub_jenis_data_ilap=bundle['jenis_data'], tipe=PIC.TipePIC.P3DE, id_user=p3de_user, start_date=date(2023, 1, 1), end_date=None)
        client.force_login(p3de_user)
        monitoring_resp = client.get(reverse('monitoring_penyampaian_data_data'), {'get_filter_options': '1'})
        assert monitoring_resp.status_code == 200
        assert 'filter_options' in json.loads(monitoring_resp.content)

    def test_bulk_document_generation_paths(self, client):
        bundle = _make_bundle()
        user = _make_p3de_user('bulk-doc')
        client.force_login(user)

        assert _is_p3de_user(user)
        assert not _is_p3de_user(None)
        assert _format_date_indonesian(None) == '-'
        assert _parse_date('2024-01-15') == date(2024, 1, 15)
        assert _parse_date('bad-date') is None
        assert _format_periode_tiket(bundle['tiket']) != '-'
        assert _base_queryset(bundle['ilap'].pk, date(2024, 1, 11)).exists()
        assert list(_apply_doc_type_filter(Tiket.objects.filter(pk=bundle['tiket'].pk), 'pkdi_lengkap'))

        status_sebagian, _ = StatusPenelitian.objects.get_or_create(deskripsi='Lengkap Sebagian')
        bundle['tiket'].id_status_penelitian = status_sebagian
        bundle['tiket'].save()
        assert list(_apply_doc_type_filter(Tiket.objects.filter(pk=bundle['tiket'].pk), 'pkdi_sebagian'))
        assert list(_apply_doc_type_filter(Tiket.objects.filter(pk=bundle['tiket'].pk), 'klarifikasi'))
        assert _apply_doc_type_filter(Tiket.objects.filter(pk=bundle['tiket'].pk), 'unknown').count() == 0
        assert _build_table_doc('Title', ['A'], [['1']]) is not None

        template_obj = SimpleNamespace(file_template=SimpleNamespace(open=lambda *args, **kwargs: BytesIO(b'PK\x03\x04fake')))
        with patch('diamond_web.views.bulk_document_generation.DocxTemplate.objects.filter', return_value=SimpleNamespace(first=lambda: template_obj)), \
             patch('diamond_web.views.bulk_document_generation.fill_template_with_data', return_value=BytesIO(b'fake-docx')):
            assert client.get(
                reverse('bulk_pkdi_klarifikasi'),
                {'ilap_id': str(bundle['ilap'].pk), 'tanggal_terima': '2024-01-11', 'doc_type': 'pkdi_sebagian'},
            ).status_code == 200
            assert client.post(
                reverse('bulk_pkdi_klarifikasi'),
                {
                    'ilap_id': str(bundle['ilap'].pk),
                    'tanggal_terima': '2024-01-11',
                    'doc_type': 'pkdi_sebagian',
                    'ticket_ids': [str(bundle['tiket'].pk)],
                },
            ).status_code == 200
            assert client.get(
                reverse('bulk_nd_pengantar_pide'),
                {'ilap_id': str(bundle['ilap'].pk), 'tanggal_kirim_pide': '2024-01-13'},
            ).status_code == 200
            assert client.post(
                reverse('bulk_nd_pengantar_pide'),
                {
                    'ilap_id': str(bundle['ilap'].pk),
                    'tanggal_kirim_pide': '2024-01-13',
                    'ticket_ids': [str(bundle['tiket'].pk)],
                },
            ).status_code == 200
