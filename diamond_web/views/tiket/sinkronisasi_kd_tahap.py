"""Sinkronisasi KD Tahap - Admin PMDE refreshes one tiket's rows per KD_TAHAP.

The tabel I query can run for minutes on a big table, longer than a web
request may take, so it runs as a Celery job (utils/kd_tahap_job.py): the
modal starts the job, polls it, and once it is done previews the change and
saves it. Same counts as the `sync_tiket_kd_tahap` command for a whole year.
"""

import hashlib
import json
import logging
from datetime import datetime

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View

from ...models.tiket import Tiket
from ...utils import format_number_with_separator
from ...utils import kd_tahap_job as jobs
from ...utils.tiket_kd_tahap import (
    QUERY_TIMEOUT,
    SCHEMA,
    STATUS_KD_TAHAP,
    KdTahapError,
    nama_tabel_i,
    simpan_kd_tahap,
    tersimpan,
    urutkan,
)
from ..mixins import is_admin_pmde
from .detail import kd_tahap_qc_lolos

logger = logging.getLogger(__name__)

TEMPLATE = 'tiket/sinkronisasi_kd_tahap_modal.html'


def _angka(value):
    return '-' if value is None else format_number_with_separator(value)


def _durasi(detik):
    if detik is None:
        return '-'
    detik = int(round(detik))
    return f'{detik // 60} menit {detik % 60} detik' if detik >= 60 else f'{detik} detik'


def _fingerprint(lama, baru):
    """Digest of the stored rows and the fetched rows the preview compared."""
    payload = {'lama': urutkan(lama), 'baru': urutkan(baru)}
    return hashlib.sha256(json.dumps(payload, default=str).encode('utf-8')).hexdigest()


def _hasil_job(job):
    """The job's fetched counts as {(kd_tahap, qc): jumlah}."""
    return {(kd, qc): jumlah for kd, qc, jumlah in job['baru']}


class _KdTahapBase(LoginRequiredMixin, UserPassesTestMixin):

    def test_func(self):
        return is_admin_pmde(self.request.user)

    def _tiket(self, pk):
        return get_object_or_404(
            Tiket.objects.select_related('id_periode_data__id_sub_jenis_data_ilap'), pk=pk,
        )

    def _render(self, tiket, job=None, pesan=None):
        lama = tersimpan(tiket)
        try:
            tabel = f'{SCHEMA}.{nama_tabel_i(tiket)}'
        except KdTahapError as exc:
            tabel, pesan = None, pesan or str(exc)
        context = {
            'tiket': tiket,
            'tabel': tabel,
            'status_berlaku': tiket.status_tiket in STATUS_KD_TAHAP,
            'tersimpan_jumlah': len({kd for kd, _ in lama}),
            'tersimpan_total': _angka(sum(lama.values())),
            'timeout_menit': QUERY_TIMEOUT // 60 if QUERY_TIMEOUT else None,
            'job': job,
            'pesan': pesan,
            'url_mulai': reverse('sinkronisasi_kd_tahap', args=[tiket.pk]),
        }
        if job:
            context['url_job'] = reverse('sinkronisasi_kd_tahap_job', args=[tiket.pk, job['id']])
            context['dibuat'] = jobs.waktu(job['dibuat'])
            context['selesai'] = jobs.waktu(job['selesai'])
            context['durasi'] = _durasi(job['durasi'])
            acuan = jobs.waktu(job['mulai'] or job['dibuat'])
            if job['state'] in (jobs.ANTRI, jobs.BERJALAN) and acuan:
                context['berjalan'] = _durasi((datetime.now() - acuan).total_seconds())
        if job and job['state'] == jobs.SELESAI:
            baru = _hasil_job(job)
            rows = [
                {
                    'kd_tahap': kunci[0] if kunci[0] is not None else '-',
                    'qc': kunci[1],
                    'lolos': kd_tahap_qc_lolos(kunci[1]),
                    'lama': _angka(lama.get(kunci)),
                    'baru': _angka(baru.get(kunci)),
                }
                for kunci, _ in urutkan({**lama, **baru})
                if lama.get(kunci) != baru.get(kunci)
            ]
            context.update({
                'changed': baru != lama,
                'rows': rows,
                'baru_jumlah': len({kd for kd, _ in baru}),
                'baru_total': _angka(sum(baru.values())),
                'fingerprint': _fingerprint(lama, baru),
            })
        return render_to_string(TEMPLATE, context, request=self.request)

    @staticmethod
    def _aktif(job):
        return bool(job) and job['state'] in (jobs.ANTRI, jobs.BERJALAN)


class SinkronisasiKdTahapView(_KdTahapBase, View):
    """GET: the tiket's KD Tahap sync, at its latest job if any. POST: start a job.

    Access Control: Admin PMDE only (`is_admin_pmde`), as Sinkronisasi dari
    Oracle. Only tikets at Pengendalian Mutu or Selesai keep KD Tahap.
    """

    def get(self, request, pk):
        tiket = self._tiket(pk)
        job = jobs.job_terakhir(tiket.pk)
        return JsonResponse({
            'html': self._render(tiket, job),
            'job_id': job['id'] if job else None,
            'aktif': self._aktif(job),
        })

    def post(self, request, pk):
        tiket = self._tiket(pk)
        if tiket.status_tiket not in STATUS_KD_TAHAP:
            return JsonResponse({
                'success': False,
                'message': 'KD Tahap hanya diambil untuk tiket berstatus Pengendalian Mutu atau Selesai.',
                'html': self._render(tiket),
            })
        try:
            nama_tabel_i(tiket)
        except KdTahapError as exc:
            return JsonResponse({'success': False, 'message': str(exc), 'html': self._render(tiket)})

        job = jobs.mulai_job(tiket, request.user)
        logger.info('Sinkronisasi KD Tahap tiket %s oleh %s: job %s (%s)',
                    tiket.nomor_tiket, request.user.username, job['id'], job['state'])
        return JsonResponse({
            'success': job['state'] != jobs.GAGAL,
            'message': job['error'] if job['state'] == jobs.GAGAL else None,
            'html': self._render(tiket, job),
            'job_id': job['id'],
            'aktif': self._aktif(job),
        })


class SinkronisasiKdTahapJobView(_KdTahapBase, View):
    """GET: a job's status (polled while it runs). POST: save its fetched rows.

    The save writes what the preview showed, provided the stored rows have not
    changed since (`fingerprint`); otherwise it shows the fresh comparison.
    """

    def _job(self, tiket, job_id):
        job = jobs.baca_job(job_id)
        if job is None or job['tiket_id'] != tiket.pk:
            raise Http404('Proses KD Tahap tidak ditemukan atau sudah kedaluwarsa.')
        return job

    def get(self, request, pk, job_id):
        tiket = self._tiket(pk)
        job = self._job(tiket, job_id)
        return JsonResponse({
            'html': self._render(tiket, job),
            'job_id': job['id'],
            'state': job['state'],
            'aktif': self._aktif(job),
        })

    def post(self, request, pk, job_id):
        tiket = self._tiket(pk)
        job = self._job(tiket, job_id)
        if job['state'] != jobs.SELESAI:
            return JsonResponse({'success': False, 'message': 'Data KD Tahap dari Oracle belum siap.',
                                 'html': self._render(tiket, job)})
        if tiket.status_tiket not in STATUS_KD_TAHAP:
            return JsonResponse({
                'success': False,
                'message': 'KD Tahap hanya disimpan untuk tiket berstatus Pengendalian Mutu atau Selesai.',
                'html': self._render(tiket, job),
            })

        baru = _hasil_job(job)
        lama = tersimpan(tiket)
        if request.POST.get('fingerprint') != _fingerprint(lama, baru):
            return JsonResponse({
                'success': False,
                'message': 'Data KD Tahap tersimpan berubah sejak pratinjau dibuka. Periksa pratinjau terbaru.',
                'html': self._render(tiket, job),
            })
        if baru == lama:
            return JsonResponse({'success': False, 'message': 'KD Tahap sudah sinkron dengan Oracle.',
                                 'html': self._render(tiket, job)})

        simpan_kd_tahap(tiket, baru)
        jobs.lupakan_job(tiket.pk)
        logger.info('Sinkronisasi KD Tahap tiket %s disimpan oleh %s: %d KD Tahap/QC, total %d baris (job %s)',
                    tiket.nomor_tiket, request.user.username, len(baru), sum(baru.values()), job['id'])
        return JsonResponse({
            'success': True,
            'message': (
                f'KD Tahap tiket {tiket.nomor_tiket} berhasil disimpan '
                f'({len({kd for kd, _ in baru})} KD Tahap, {len(baru)} baris KD Tahap/QC).'
            ),
        })
