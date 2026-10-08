"""Background job yang mengambil KD Tahap satu tiket dari Oracle (Celery).

Query ke tabel I bisa berjalan beberapa menit untuk tabel besar, lebih lama
dari batas waktu request web. Karena itu halaman detil tiket hanya memulai job
(`mulai_job`) lalu menanyakan statusnya (`baca_job`); query-nya dijalankan
worker Celery (`jalankan_job`). Status & hasil job disimpan di cache (Redis),
yang dibagi web dan worker:

    kd_tahap_job_<job_id>       -> dict status job (lihat `mulai_job`)
    kd_tahap_job_tiket_<tiket>  -> job_id terakhir milik tiket itu
    kd_tahap_jobs_aktif         -> job_id yang antri/berjalan, untuk daftar antrian

Job dapat dihentikan (`hentikan_job`): job yang antri dilewati worker. Untuk
job yang berjalan, worker langsung dilepas untuk job berikutnya dan query-nya
dibatalkan lewat connection.cancel(). Oracle baru menanggapi pembatalan itu
di akhir full scan, jadi query tetap berjalan di Oracle sampai saat itu (paling
lama QUERY_TIMEOUT) di thread latar yang hasilnya dibuang.
"""

import logging
import threading
import uuid
from datetime import datetime

from django.core.cache import cache

from . import tiket_kd_tahap
from .tiket_kd_tahap import QUERY_TIMEOUT, KdTahapError, ambil_kd_tahap_tiket

logger = logging.getLogger(__name__)

# Lama job & hasilnya disimpan.
JOB_TTL = 6 * 3600

ANTRI = 'antri'        # menunggu worker Celery
BERJALAN = 'berjalan'  # worker sedang query Oracle
SELESAI = 'selesai'    # hasil siap untuk dipratinjau & disimpan
GAGAL = 'gagal'
DIHENTIKAN = 'dihentikan'  # dihentikan pengguna

AKTIF = (ANTRI, BERJALAN)

_KEY_AKTIF = 'kd_tahap_jobs_aktif'

# Job yang "berjalan" lebih lama dari ini tanpa kabar dianggap worker-nya mati.
_BATAS_BERJALAN = (QUERY_TIMEOUT or 3600) + 300

_FORMAT_WAKTU = '%Y-%m-%dT%H:%M:%S'


def _key_job(job_id):
    return f'kd_tahap_job_{job_id}'


def _key_tiket(tiket_id):
    return f'kd_tahap_job_tiket_{tiket_id}'


def _sekarang():
    return datetime.now().strftime(_FORMAT_WAKTU)


def waktu(teks):
    return datetime.strptime(teks, _FORMAT_WAKTU) if teks else None


def _simpan(job):
    cache.set(_key_job(job['id']), job, timeout=JOB_TTL)


def _ubah(job_id, **fields):
    job = cache.get(_key_job(job_id))
    if job is None:
        return None
    job.update(fields)
    _simpan(job)
    return job


def _akhiri(job_id, **fields):
    """Tulis hasil akhir job, kecuali job sudah dihentikan pengguna."""
    job = cache.get(_key_job(job_id))
    if job is None or job['state'] == DIHENTIKAN:
        return job
    job.update(fields)
    _simpan(job)
    return job


def _dihentikan(job_id):
    job = cache.get(_key_job(job_id))
    return bool(job) and job['state'] == DIHENTIKAN


def baca_job(job_id):
    """Status job, atau None bila tidak ada / kedaluwarsa.

    Job yang "berjalan" melewati batas tanpa selesai ditandai gagal: worker-nya
    berhenti di tengah jalan (restart, crash) dan tidak akan melapor lagi.
    """
    job = cache.get(_key_job(job_id))
    if job and job['state'] == SELESAI and any(len(baris) != 3 for baris in job['baru'] or []):
        # Hasil versi sebelumnya ([kd_tahap, jumlah], tanpa QC) tidak dapat disimpan.
        return _ubah(job_id, state=GAGAL, error='Hasil ini diambil sebelum ada kolom QC. Silakan ambil ulang.')
    if job and job['state'] == BERJALAN:
        mulai = waktu(job['mulai'])
        if mulai and (datetime.now() - mulai).total_seconds() > _BATAS_BERJALAN:
            job = _ubah(job_id, state=GAGAL, selesai=_sekarang(), error=(
                'Tidak ada kabar dari worker setelah {} menit; proses kemungkinan terhenti. '
                'Silakan coba lagi.'.format(_BATAS_BERJALAN // 60)
            ))
    return job


def job_terakhir(tiket_id):
    """Job terakhir milik tiket (aktif atau sudah selesai), atau None."""
    job_id = cache.get(_key_tiket(tiket_id))
    return baca_job(job_id) if job_id else None


def lupakan_job(tiket_id):
    """Lepas job terakhir dari tiket (mis. setelah hasilnya disimpan)."""
    cache.delete(_key_tiket(tiket_id))


def mulai_job(tiket, user):
    """Mulai (atau pakai lagi) job untuk tiket; kembalikan dict status job.

    Job yang masih antri/berjalan untuk tiket yang sama dipakai lagi, supaya
    klik berulang tidak menumpuk query berat di Oracle.
    """
    from ..tasks import ambil_kd_tahap_tiket_task

    aktif = job_terakhir(tiket.pk)
    if aktif and aktif['state'] in (ANTRI, BERJALAN):
        return aktif

    job = {
        'id': uuid.uuid4().hex,
        'tiket_id': tiket.pk,
        'nomor_tiket': tiket.nomor_tiket,
        'user': user.username,
        'state': ANTRI,
        'dibuat': _sekarang(),
        'mulai': None,
        'selesai': None,
        'durasi': None,
        'baru': None,      # [[kd_tahap, qc, jumlah], ...] saat selesai
        'error': None,
        'timeout': False,
        'task_id': None,
        'dihentikan_oleh': None,
    }
    _simpan(job)
    cache.set(_key_tiket(tiket.pk), job['id'], timeout=JOB_TTL)
    _daftar_aktif(tambah=job['id'])
    try:
        hasil = ambil_kd_tahap_tiket_task.delay(job['id'])
    except Exception as exc:  # broker (Redis) mati, Celery tidak terpasang, ...
        logger.exception('KD Tahap tiket %s: gagal mengirim job ke Celery', tiket.nomor_tiket)
        return _ubah(job['id'], state=GAGAL, selesai=_sekarang(), error=(
            f'Worker latar belakang (Celery) tidak dapat dihubungi: {exc}'
        )) or job
    # Kept to revoke a job stopped while it still waits in the broker queue.
    task_id = getattr(hasil, 'id', None)
    if isinstance(task_id, str):
        job = _ubah(job['id'], task_id=task_id) or job
    return job


def hentikan_job(job_id, user):
    """Hentikan job yang antri/berjalan; kembalikan dict status job.

    Status langsung menjadi "dihentikan". Job yang antri dilewati worker saat
    gilirannya tiba; query job yang berjalan dibatalkan worker lewat
    connection.cancel() (Oracle bisa butuh beberapa detik untuk berhenti).
    """
    job = baca_job(job_id)
    if job is None or job['state'] not in AKTIF:
        return job
    job = _ubah(job_id, state=DIHENTIKAN, selesai=_sekarang(), dihentikan_oleh=user.username)
    _daftar_aktif()
    if job.get('task_id') and job.get('mulai') is None:
        try:
            from celery import current_app
            current_app.control.revoke(job['task_id'])
        except Exception as exc:  # the stop flag alone already makes the worker skip it
            logger.warning('KD Tahap job %s: revoke gagal: %s', job_id, exc)
    logger.info('KD Tahap job %s (tiket %s) dihentikan oleh %s', job_id, job.get('nomor_tiket'), user.username)
    return job


def _daftar_aktif(tambah=None):
    """Daftar job yang antri/berjalan, terurut menurut waktu diminta.

    Job yang sudah tidak aktif dibuang dari daftar. Daftar ini hanya untuk
    tampilan antrian, jadi update yang sesekali tertimpa tidak berbahaya.
    """
    ids = list(cache.get(_KEY_AKTIF) or [])
    if tambah and tambah not in ids:
        ids.append(tambah)
    jobs = [job for job in (baca_job(job_id) for job_id in ids) if job and job['state'] in AKTIF]
    cache.set(_KEY_AKTIF, [job['id'] for job in jobs], timeout=JOB_TTL)
    return sorted(jobs, key=lambda job: job['dibuat'])


def antrian():
    """Job Sinkronisasi KD Tahap yang antri/berjalan (semua tiket), urut waktu diminta."""
    return _daftar_aktif()


def panjang_antrian_worker():
    """Jumlah tugas Celery yang menunggu di antrian broker (semua jenis), atau None.

    Dibaca langsung dari broker: worker `solo` yang sedang sibuk tidak bisa
    menjawab `inspect`. Disimpan 5 detik agar polling tidak membebani Redis.
    """
    jumlah = cache.get('kd_tahap_antrian_worker')
    if jumlah is not None:
        return jumlah
    try:
        from celery import current_app
        with current_app.connection_for_read() as conn:
            conn.ensure_connection(max_retries=1, timeout=2)
            nama = current_app.conf.task_default_queue or 'celery'
            jumlah = conn.default_channel.queue_declare(queue=nama, passive=True).message_count
    except Exception as exc:
        logger.debug('Panjang antrian Celery tidak terbaca: %s', exc)
        return None
    cache.set('kd_tahap_antrian_worker', jumlah, timeout=5)
    return jumlah


def _query_dengan_berhenti(job_id, service, tiket):
    """Jalankan query di thread sendiri; None bila job dihentikan sebelum selesai.

    cursor.execute() memblok sampai Oracle selesai, dan Oracle baru menanggapi
    connection.cancel() di akhir full scan. Dengan query di thread terpisah,
    worker cukup menunggu sambil memeriksa permintaan berhenti, lalu kembali
    seketika saat dihentikan; thread query (daemon) dibiarkan selesai sendiri.
    Error query diteruskan ke pemanggil.
    """
    hasil = {}

    def _query():
        try:
            hasil['hitungan'] = ambil_kd_tahap_tiket(service, tiket, stop_checker=lambda: _dihentikan(job_id))
        except BaseException as exc:  # noqa: B902 - diteruskan ke thread worker
            hasil['error'] = exc

    thread = threading.Thread(target=_query, name=f'kd_tahap_{job_id[:8]}', daemon=True)
    thread.start()
    while thread.is_alive():
        thread.join(tiket_kd_tahap.INTERVAL_CEK_BERHENTI)
        if thread.is_alive() and _dihentikan(job_id):
            return None
    if 'error' in hasil:
        raise hasil['error']
    return hasil['hitungan']


def jalankan_job(job_id):
    """Dijalankan worker Celery: query Oracle lalu tulis hasilnya ke job."""
    from ..models.tiket import Tiket
    from .oracle_sync import OracleDataSyncService, OracleSyncConfigError

    job = cache.get(_key_job(job_id))
    if job is None:
        logger.warning('KD Tahap job %s tidak ditemukan (kedaluwarsa?)', job_id)
        return
    if job['state'] == DIHENTIKAN:
        logger.info('KD Tahap job %s dilewati: dihentikan oleh %s saat antri', job_id, job.get('dihentikan_oleh'))
        return
    job = _akhiri(job_id, state=BERJALAN, mulai=_sekarang())
    if job is None or job['state'] == DIHENTIKAN:
        return
    t0 = datetime.now()

    def _durasi():
        return (datetime.now() - t0).total_seconds()

    try:
        tiket = Tiket.objects.select_related('id_periode_data__id_sub_jenis_data_ilap').get(pk=job['tiket_id'])
        logger.info('KD Tahap job %s: tiket %s mulai', job_id, tiket.nomor_tiket)
        hitungan = _query_dengan_berhenti(job_id, OracleDataSyncService(connection_only=True), tiket)
        if hitungan is None:
            logger.info('KD Tahap job %s: dihentikan setelah %.1f detik; worker dilepas, query Oracle '
                        'dibatalkan di latar', job_id, _durasi())
            _ubah(job_id, durasi=_durasi())
            return
    except KdTahapError as exc:
        if exc.dihentikan or _dihentikan(job_id):
            logger.info('KD Tahap job %s: query dibatalkan setelah %.1f detik', job_id, _durasi())
            _ubah(job_id, durasi=_durasi())
            return
        _akhiri(job_id, state=GAGAL, selesai=_sekarang(), error=str(exc), timeout=exc.timeout, durasi=_durasi())
        return
    except (OracleSyncConfigError, Tiket.DoesNotExist) as exc:
        _akhiri(job_id, state=GAGAL, selesai=_sekarang(), error=str(exc) or exc.__class__.__name__,
                durasi=_durasi())
        return
    except Exception as exc:
        logger.exception('KD Tahap job %s gagal', job_id)
        _akhiri(job_id, state=GAGAL, selesai=_sekarang(), error=f'Error tak terduga: {exc}', durasi=_durasi())
        return

    durasi = _durasi()
    job = _akhiri(job_id, state=SELESAI, selesai=_sekarang(), durasi=durasi,
                  baru=[[kd, qc, jumlah] for (kd, qc), jumlah in hitungan.items()])
    if job and job['state'] == DIHENTIKAN:
        logger.info('KD Tahap job %s: hasil dibuang, dihentikan saat query hampir selesai', job_id)
        return
    logger.info('KD Tahap job %s: %d KD Tahap/QC dalam %.1f detik', job_id, len(hitungan), durasi)
