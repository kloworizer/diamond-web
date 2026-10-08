"""Background job yang mengambil KD Tahap satu tiket dari Oracle (Celery).

Query ke tabel I bisa berjalan beberapa menit untuk tabel besar, lebih lama
dari batas waktu request web. Karena itu halaman detil tiket hanya memulai job
(`mulai_job`) lalu menanyakan statusnya (`baca_job`); query-nya dijalankan
worker Celery (`jalankan_job`). Status & hasil job disimpan di cache (Redis),
yang dibagi web dan worker:

    kd_tahap_job_<job_id>       -> dict status job (lihat `_job_baru`)
    kd_tahap_job_tiket_<tiket>  -> job_id terakhir milik tiket itu
"""

import logging
import uuid
from datetime import datetime

from django.core.cache import cache

from .tiket_kd_tahap import QUERY_TIMEOUT, KdTahapError, ambil_kd_tahap_tiket

logger = logging.getLogger(__name__)

# Lama job & hasilnya disimpan.
JOB_TTL = 6 * 3600

ANTRI = 'antri'        # menunggu worker Celery
BERJALAN = 'berjalan'  # worker sedang query Oracle
SELESAI = 'selesai'    # hasil siap untuk dipratinjau & disimpan
GAGAL = 'gagal'

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
        'user': user.username,
        'state': ANTRI,
        'dibuat': _sekarang(),
        'mulai': None,
        'selesai': None,
        'durasi': None,
        'baru': None,      # [[kd_tahap, qc, jumlah], ...] saat selesai
        'error': None,
        'timeout': False,
    }
    _simpan(job)
    cache.set(_key_tiket(tiket.pk), job['id'], timeout=JOB_TTL)
    try:
        ambil_kd_tahap_tiket_task.delay(job['id'])
    except Exception as exc:  # broker (Redis) mati, Celery tidak terpasang, ...
        logger.exception('KD Tahap tiket %s: gagal mengirim job ke Celery', tiket.nomor_tiket)
        job = _ubah(job['id'], state=GAGAL, selesai=_sekarang(), error=(
            f'Worker latar belakang (Celery) tidak dapat dihubungi: {exc}'
        )) or job
    return job


def jalankan_job(job_id):
    """Dijalankan worker Celery: query Oracle lalu tulis hasilnya ke job."""
    from ..models.tiket import Tiket
    from .oracle_sync import OracleDataSyncService, OracleSyncConfigError

    job = _ubah(job_id, state=BERJALAN, mulai=_sekarang())
    if job is None:
        logger.warning('KD Tahap job %s tidak ditemukan (kedaluwarsa?)', job_id)
        return
    t0 = datetime.now()
    try:
        tiket = Tiket.objects.select_related('id_periode_data__id_sub_jenis_data_ilap').get(pk=job['tiket_id'])
        logger.info('KD Tahap job %s: tiket %s mulai', job_id, tiket.nomor_tiket)
        hitungan = ambil_kd_tahap_tiket(OracleDataSyncService(connection_only=True), tiket)
    except KdTahapError as exc:
        _ubah(job_id, state=GAGAL, selesai=_sekarang(), error=str(exc), timeout=exc.timeout,
              durasi=(datetime.now() - t0).total_seconds())
        return
    except (OracleSyncConfigError, Tiket.DoesNotExist) as exc:
        _ubah(job_id, state=GAGAL, selesai=_sekarang(), error=str(exc) or exc.__class__.__name__,
              durasi=(datetime.now() - t0).total_seconds())
        return
    except Exception as exc:
        logger.exception('KD Tahap job %s gagal', job_id)
        _ubah(job_id, state=GAGAL, selesai=_sekarang(), error=f'Error tak terduga: {exc}',
              durasi=(datetime.now() - t0).total_seconds())
        return

    durasi = (datetime.now() - t0).total_seconds()
    _ubah(job_id, state=SELESAI, selesai=_sekarang(), durasi=durasi,
          baru=[[kd, qc, jumlah] for (kd, qc), jumlah in hitungan.items()])
    logger.info('KD Tahap job %s: %d KD Tahap/QC dalam %.1f detik', job_id, len(hitungan), durasi)
