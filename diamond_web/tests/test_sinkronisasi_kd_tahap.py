"""Sinkronisasi KD Tahap: Admin PMDE refreshes one tiket's KD Tahap from its detail page.

The tabel I query runs as a Celery job (utils/kd_tahap_job.py) so a big table
cannot time out the request: the modal starts the job, polls it, previews the
result and saves it.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse

from diamond_web.constants.tiket_status import STATUS_IDENTIFIKASI, STATUS_PENGENDALIAN_MUTU, STATUS_SELESAI
from diamond_web.models.tiket_kd_tahap import TiketKdTahap
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.utils import kd_tahap_job as jobs
from diamond_web.utils.tiket_kd_tahap import KdTahapError

from .conftest import TiketFactory, TiketPICFactory

AMBIL = 'diamond_web.utils.kd_tahap_job.ambil_kd_tahap_tiket'
DELAY = 'diamond_web.tasks.ambil_kd_tahap_tiket_task.delay'


@pytest.fixture(autouse=True)
def _cache(settings):
    """The job state lives in the cache Redis provides in production."""
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                   'LOCATION': 'kd-tahap-tests'}}
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def tiket(db):
    tiket = TiketFactory(status_tiket=STATUS_SELESAI)
    jdi = tiket.id_periode_data.id_sub_jenis_data_ilap
    jdi.nama_tabel_I = 'KPDE_CONTOH'
    jdi.save()
    return tiket


def _url(tiket):
    return reverse('sinkronisasi_kd_tahap', args=[tiket.pk])


def _job_url(tiket, job_id):
    return reverse('sinkronisasi_kd_tahap_job', args=[tiket.pk, job_id])


def _simpanan(tiket):
    return {
        (kd, qc): jumlah
        for kd, qc, jumlah in TiketKdTahap.objects.filter(id_tiket=tiket).values_list('kd_tahap', 'qc', 'jumlah_baris')
    }


def _mulai(client, tiket):
    """Start a job; Celery only receives it (the job stays queued)."""
    with patch(DELAY) as delay:
        data = client.post(_url(tiket)).json()
    return data, delay


def _jalankan(job_id, hasil):
    """Run the job as the Celery worker would, with *hasil* from Oracle."""
    kwargs = {'side_effect': hasil} if isinstance(hasil, Exception) else {'return_value': hasil}
    with patch(AMBIL, **kwargs):
        jobs.jalankan_job(job_id)


def _fingerprint(html):
    import re
    return re.search(r'name="fingerprint" value="([0-9a-f]+)"', html).group(1)


@pytest.mark.django_db
class TestAkses:

    def test_hanya_admin_pmde(self, client, pide_admin_user, pmde_user, tiket):
        for user in (pide_admin_user, pmde_user):
            TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PMDE, active=True)
            client.force_login(user)
            assert client.get(_url(tiket)).status_code == 403
            assert client.post(_url(tiket)).status_code == 403
            assert client.get(_job_url(tiket, 'x')).status_code == 403

    @pytest.mark.parametrize('status, tampil', [
        (STATUS_SELESAI, True), (STATUS_PENGENDALIAN_MUTU, True), (STATUS_IDENTIFIKASI, False),
    ])
    def test_tombol_di_detail_untuk_pengendalian_mutu_dan_selesai(self, client, pmde_admin_user, tiket, status, tampil):
        tiket.status_tiket = status
        tiket.save()
        client.force_login(pmde_admin_user)
        html = client.get(reverse('tiket_detail', args=[tiket.pk])).content.decode()
        assert ('id="sinkronisasi-kd-tahap-btn"' in html) is tampil
        assert ('id="sinkronisasiKdTahapModal"' in html) is tampil
        assert 'id="sinkronisasi-tiket-btn"' in html  # Sinkronisasi dari Oracle stays

    def test_sinkronisasi_dari_oracle_tidak_lagi_mengambil_kd_tahap(self, client, pmde_admin_user, tiket):
        client.force_login(pmde_admin_user)
        with patch('diamond_web.views.tiket.sinkronisasi_tiket._fetch_row', return_value=(None, None)), \
                patch('diamond_web.utils.tiket_kd_tahap.ambil_kd_tahap_tiket') as ambil:
            html = client.get(reverse('sinkronisasi_tiket', args=[tiket.pk])).json()['html']
        ambil.assert_not_called()
        assert 'KD Tahap' not in html


@pytest.mark.django_db
class TestAlur:

    def test_awal_menampilkan_data_tersimpan_dan_tombol_ambil(self, client, pmde_admin_user, tiket):
        TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='A', jumlah_baris=1500)
        client.force_login(pmde_admin_user)

        data = client.get(_url(tiket)).json()

        assert data['job_id'] is None and data['aktif'] is False
        assert 'data-kd-state="awal"' in data['html']
        assert 'BANKDATAPDE.KPDE_CONTOH' in data['html']
        assert '<strong class="text-dark">1</strong> KD Tahap, total <strong class="text-dark">1.500</strong>' in data['html']
        assert 'data-kd-action="mulai"' in data['html']

    def test_mulai_mengantrikan_job_dan_klik_ulang_memakai_job_yang_sama(self, client, pmde_admin_user, tiket):
        client.force_login(pmde_admin_user)

        data, delay = _mulai(client, tiket)
        assert data['success'] is True and data['aktif'] is True
        assert 'data-kd-state="antri"' in data['html']
        delay.assert_called_once_with(data['job_id'])

        lagi, delay2 = _mulai(client, tiket)
        assert lagi['job_id'] == data['job_id']
        delay2.assert_not_called()

        # Reopening the modal resumes the running job.
        buka = client.get(_url(tiket)).json()
        assert buka['job_id'] == data['job_id'] and buka['aktif'] is True

    def test_selesai_pratinjau_lalu_simpan(self, client, pmde_admin_user, tiket):
        TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='A', qc='P', jumlah_baris=5)
        TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='B', qc='P', jumlah_baris=2)
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, tiket)[0]['job_id']

        _jalankan(job_id, {('A', 'P'): 5, ('C', 'X'): 1500, (None, None): 3})
        data = client.get(_job_url(tiket, job_id)).json()

        assert data['state'] == 'selesai' and data['aktif'] is False
        html = data['html']
        assert 'data-kd-state="selesai"' in html
        assert 'Total baris 7 → <strong>1.508</strong>; 3 baris KD Tahap/QC berubah' in html
        assert '>B<' in html and '>C<' in html and '>A<' not in html
        assert 'title="Lolos QC">X<' in html and 'Belum QC' in html
        assert _simpanan(tiket) == {('A', 'P'): 5, ('B', 'P'): 2}  # nothing saved by the preview

        hasil = client.post(_job_url(tiket, job_id), {'fingerprint': _fingerprint(html)}).json()
        assert hasil['success'] is True
        assert _simpanan(tiket) == {('A', 'P'): 5, ('C', 'X'): 1500, (None, None): 3}

        # The job is let go: the next opening starts afresh with the new data.
        buka = client.get(_url(tiket)).json()
        assert buka['job_id'] is None and 'data-kd-state="awal"' in buka['html']

    def test_sudah_sinkron_tanpa_tombol_simpan(self, client, pmde_admin_user, tiket):
        TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='A', jumlah_baris=5)
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, tiket)[0]['job_id']

        _jalankan(job_id, {('A', None): 5})
        html = client.get(_job_url(tiket, job_id)).json()['html']

        assert 'data-kd-sinkron' in html
        assert 'type="submit"' not in html
        assert 'Ambil Ulang' in html

    def test_data_tersimpan_berubah_setelah_pratinjau_tidak_disimpan(self, client, pmde_admin_user, tiket):
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, tiket)[0]['job_id']
        _jalankan(job_id, {('A', None): 5})
        fingerprint = _fingerprint(client.get(_job_url(tiket, job_id)).json()['html'])

        TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='Z', jumlah_baris=1)
        hasil = client.post(_job_url(tiket, job_id), {'fingerprint': fingerprint}).json()

        assert hasil['success'] is False and 'berubah sejak pratinjau' in hasil['message']
        assert _simpanan(tiket) == {('Z', None): 1}


@pytest.mark.django_db
class TestGagal:

    def test_timeout_ditampilkan_dan_bisa_dicoba_lagi(self, client, pmde_admin_user, tiket):
        TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='A', jumlah_baris=5)
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, tiket)[0]['job_id']

        _jalankan(job_id, KdTahapError(
            'BANKDATAPDE.KPDE_CONTOH: query melewati batas waktu 900 detik (DPY-4011)', timeout=True,
        ))
        data = client.get(_job_url(tiket, job_id)).json()

        assert data['state'] == 'gagal'
        assert 'Query melewati batas waktu' in data['html'] and 'DPY-4011' in data['html']
        assert 'Coba Lagi' in data['html']
        assert _simpanan(tiket) == {('A', None): 5}

        # Coba Lagi starts a new job rather than reusing the failed one.
        lagi, delay = _mulai(client, tiket)
        assert lagi['job_id'] != job_id
        delay.assert_called_once()

    def test_celery_tidak_tersedia(self, client, pmde_admin_user, tiket):
        client.force_login(pmde_admin_user)
        with patch(DELAY, side_effect=ConnectionError('Error 10061 connecting to localhost:6379')):
            data = client.post(_url(tiket)).json()

        assert data['success'] is False and data['aktif'] is False
        assert 'Celery' in data['message'] and '6379' in data['message']
        assert 'data-kd-state="gagal"' in data['html']

    def test_job_berjalan_tanpa_kabar_dianggap_gagal(self, client, pmde_admin_user, tiket, monkeypatch):
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, tiket)[0]['job_id']
        lama = (datetime.now() - timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%S')
        jobs._ubah(job_id, state=jobs.BERJALAN, mulai=lama)

        data = client.get(_job_url(tiket, job_id)).json()

        assert data['state'] == 'gagal' and 'Tidak ada kabar dari worker' in data['html']

    def test_status_lain_ditolak(self, client, pmde_admin_user, tiket):
        tiket.status_tiket = STATUS_IDENTIFIKASI
        tiket.save()
        client.force_login(pmde_admin_user)

        data, delay = _mulai(client, tiket)

        assert data['success'] is False and 'Pengendalian Mutu atau Selesai' in data['message']
        delay.assert_not_called()

    def test_job_tiket_lain_tidak_ditemukan(self, client, pmde_admin_user, tiket):
        lain = TiketFactory(status_tiket=STATUS_SELESAI)
        jdi = lain.id_periode_data.id_sub_jenis_data_ilap
        jdi.nama_tabel_I = 'KPDE_LAIN'
        jdi.save()
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, lain)[0]['job_id']

        assert client.get(_job_url(tiket, job_id)).status_code == 404
        assert client.post(_job_url(tiket, job_id), {'fingerprint': 'x'}).status_code == 404


@pytest.mark.django_db
def test_hasil_job_versi_lama_tanpa_qc_minta_ambil_ulang(client, pmde_admin_user, tiket):
    client.force_login(pmde_admin_user)
    job_id = _mulai(client, tiket)[0]['job_id']
    jobs._ubah(job_id, state=jobs.SELESAI, baru=[['A', 5]])  # stored before the QC column

    data = client.get(_job_url(tiket, job_id)).json()

    assert data['state'] == 'gagal' and 'sebelum ada kolom QC' in data['html']
    assert 'Coba Lagi' in data['html']


ANTRIAN_WORKER = 'diamond_web.utils.kd_tahap_job.panjang_antrian_worker'


@pytest.fixture(autouse=True)
def _antrian_worker():
    """The broker queue length is read from Redis; tests stub it."""
    with patch(ANTRIAN_WORKER, return_value=3) as stub:
        yield stub


def _hentikan_url(tiket, job_id):
    return reverse('sinkronisasi_kd_tahap_hentikan', args=[tiket.pk, job_id])


def _tiket_lain(nama_tabel):
    lain = TiketFactory(status_tiket=STATUS_SELESAI)
    jdi = lain.id_periode_data.id_sub_jenis_data_ilap
    jdi.nama_tabel_I = nama_tabel
    jdi.save()
    return lain


@pytest.mark.django_db
class TestAntrian:

    def test_daftar_antrian_dan_posisi_tiket(self, client, pmde_admin_user, tiket):
        client.force_login(pmde_admin_user)
        pertama, kedua = _tiket_lain('KPDE_A'), _tiket_lain('KPDE_B')
        id_pertama = _mulai(client, pertama)[0]['job_id']
        _mulai(client, kedua)
        jobs._ubah(id_pertama, state=jobs.BERJALAN, mulai=jobs._sekarang())

        html = _mulai(client, tiket)[0]['html']

        assert 'Antrian Sinkronisasi KD Tahap' in html
        assert 'Antrian worker: 3 tugas menunggu' in html
        assert '<strong>2</strong> proses KD Tahap lain di depan tiket ini' in html
        urutan = [html.index(t) for t in (pertama.nomor_tiket, kedua.nomor_tiket, tiket.nomor_tiket)]
        assert urutan == sorted(urutan)
        assert 'tiket ini</span>' in html and 'data-kd-antrian-ini' in html
        assert html.count('>Berjalan</span>') == 1 and html.count('>Menunggu</span>') == 2
        assert 'href="{}"'.format(reverse('tiket_detail', args=[pertama.pk])) in html
        assert 'data-kd-action="hentikan"' in html

    def test_job_selesai_keluar_dari_antrian(self, client, pmde_admin_user, tiket):
        client.force_login(pmde_admin_user)
        lain = _tiket_lain('KPDE_A')
        id_lain = _mulai(client, lain)[0]['job_id']
        _jalankan(id_lain, {('A', 'P'): 1})

        html = _mulai(client, tiket)[0]['html']

        assert lain.nomor_tiket not in html
        assert 'Tiket ini berikutnya' in html

    def test_antrian_worker_tidak_terbaca(self, client, pmde_admin_user, tiket, _antrian_worker):
        _antrian_worker.return_value = None
        client.force_login(pmde_admin_user)

        html = _mulai(client, tiket)[0]['html']

        assert 'Antrian worker:' not in html
        assert 'Antrian Sinkronisasi KD Tahap' in html


@pytest.mark.django_db
class TestHentikan:

    def test_hentikan_job_antri_dilewati_worker(self, client, pmde_admin_user, tiket):
        client.force_login(pmde_admin_user)
        with patch(DELAY) as delay:
            delay.return_value.id = 'task-1'
            job_id = client.post(_url(tiket)).json()['job_id']

        with patch('celery.app.control.Control.revoke') as revoke:
            data = client.post(_hentikan_url(tiket, job_id)).json()

        assert data['success'] is True and data['aktif'] is False
        assert 'data-kd-dihentikan' in data['html'] and pmde_admin_user.username in data['html']
        assert 'sebelum mulai' in data['html']
        revoke.assert_called_once_with('task-1')

        with patch(AMBIL) as ambil:
            jobs.jalankan_job(job_id)
        ambil.assert_not_called()
        assert jobs.baca_job(job_id)['state'] == jobs.DIHENTIKAN
        assert jobs.antrian() == []

        # The modal offers a fresh start.
        lagi = client.get(_url(tiket)).json()
        assert 'data-kd-dihentikan' in lagi['html'] and 'Ambil dari Oracle' in lagi['html']
        assert _mulai(client, tiket)[0]['job_id'] != job_id

    def test_hentikan_job_berjalan_membatalkan_query(self, client, pmde_admin_user, tiket):
        TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='A', jumlah_baris=5)
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, tiket)[0]['job_id']

        def _query(service, t, stop_checker):
            # Runs in the worker's query thread: the stop arrives while Oracle
            # is still busy, and the watcher sees it.
            assert stop_checker() is False
            jobs.hentikan_job(job_id, pmde_admin_user)
            assert stop_checker() is True
            raise KdTahapError('BANKDATAPDE.KPDE_CONTOH: query dibatalkan (DPY-4011)', dihentikan=True)

        with patch(AMBIL, side_effect=_query):
            jobs.jalankan_job(job_id)

        job = jobs.baca_job(job_id)
        assert job['state'] == jobs.DIHENTIKAN and job['error'] is None
        assert job['durasi'] is not None
        html = client.get(_job_url(tiket, job_id)).json()['html']
        assert 'setelah query berjalan' in html
        assert _simpanan(tiket) == {('A', None): 5}

    def test_hasil_yang_datang_setelah_dihentikan_dibuang(self, client, pmde_admin_user, tiket):
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, tiket)[0]['job_id']

        def _query(service, t, stop_checker):
            jobs.hentikan_job(job_id, pmde_admin_user)
            return {('A', 'P'): 9}  # Oracle finished just before the cancel landed

        with patch(AMBIL, side_effect=_query):
            jobs.jalankan_job(job_id)

        job = jobs.baca_job(job_id)
        assert job['state'] == jobs.DIHENTIKAN and job['baru'] is None

    def test_worker_dilepas_seketika_walau_oracle_belum_berhenti(
            self, client, pmde_admin_user, tiket, monkeypatch):
        """Oracle answers a cancel only at the end of its scan: the worker must not wait for it."""
        import threading
        import time

        from diamond_web.utils import tiket_kd_tahap

        monkeypatch.setattr(tiket_kd_tahap, 'INTERVAL_CEK_BERHENTI', 0.05)
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, tiket)[0]['job_id']
        mulai_query, lepas_oracle = threading.Event(), threading.Event()

        def _query(service, t, stop_checker):
            mulai_query.set()
            lepas_oracle.wait(10)  # Oracle still scanning, cancel or not
            return {('A', 'P'): 9}

        def _hentikan_saat_berjalan():
            mulai_query.wait(5)
            jobs.hentikan_job(job_id, pmde_admin_user)

        penghenti = threading.Thread(target=_hentikan_saat_berjalan)
        penghenti.start()
        t0 = time.monotonic()
        try:
            with patch(AMBIL, side_effect=_query):
                jobs.jalankan_job(job_id)
            lama = time.monotonic() - t0
        finally:
            lepas_oracle.set()
            penghenti.join()

        assert lama < 3
        job = jobs.baca_job(job_id)
        assert job['state'] == jobs.DIHENTIKAN and job['baru'] is None

    def test_job_yang_sudah_selesai_tidak_bisa_dihentikan(self, client, pmde_admin_user, tiket):
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, tiket)[0]['job_id']
        _jalankan(job_id, {('A', None): 1})

        data = client.post(_hentikan_url(tiket, job_id)).json()

        assert data['success'] is False and 'sudah tidak berjalan' in data['message']
        assert jobs.baca_job(job_id)['state'] == jobs.SELESAI

    def test_hanya_admin_pmde(self, client, pide_admin_user, pmde_admin_user, tiket):
        client.force_login(pmde_admin_user)
        job_id = _mulai(client, tiket)[0]['job_id']
        client.force_login(pide_admin_user)

        assert client.post(_hentikan_url(tiket, job_id)).status_code == 403
        assert jobs.baca_job(job_id)['state'] == jobs.ANTRI


def test_penjaga_membatalkan_query_saat_diminta_berhenti(monkeypatch):
    """ambil_kd_tahap_tiket cancels the running query once stop_checker() is True."""
    import threading
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from diamond_web.utils import tiket_kd_tahap

    monkeypatch.setattr(tiket_kd_tahap, 'INTERVAL_CEK_BERHENTI', 0.05)
    dibatalkan = threading.Event()

    def _execute(sql, params):
        # Oracle stays busy until the cancel arrives, then drops the connection.
        assert dibatalkan.wait(5), 'query was never cancelled'
        raise Exception('DPY-4011: the database or network closed the connection\nORA-03135')

    cursor = MagicMock()
    cursor.execute.side_effect = _execute
    conn = MagicMock()
    conn.cancel.side_effect = dibatalkan.set

    @contextmanager
    def _cursor_cm():
        yield cursor

    conn.cursor.side_effect = _cursor_cm

    @contextmanager
    def _connect(_which):
        yield conn

    service = MagicMock()
    service._connect_oracle.side_effect = _connect
    jdi = SimpleNamespace(nama_tabel_I='KPDE_CONTOH')
    tiket = SimpleNamespace(id=1, nomor_tiket='T0000000000000001',
                            id_periode_data=SimpleNamespace(id_sub_jenis_data_ilap=jdi))
    cek = iter([False, False, True])

    with pytest.raises(KdTahapError) as err:
        tiket_kd_tahap.ambil_kd_tahap_tiket(service, tiket, stop_checker=lambda: next(cek, True))

    assert err.value.dihentikan is True and err.value.timeout is False
    conn.cancel.assert_called_once()
