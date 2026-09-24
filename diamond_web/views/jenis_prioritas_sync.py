"""Tombol "Sinkronisasi Prioritas" di halaman Daftar Jenis Prioritas Data.

Menyelaraskan ``Tiket.id_jenis_prioritas_data`` seluruh tiket dengan isi tabel
``jenis_prioritas_data``: tiket yang tanggal terima DIP-nya masuk masa berlaku
sebuah record jadi prioritas, yang tidak jadi tidak prioritas. Aturannya sama
dengan perintah ``backfill_tiket_jenis_prioritas`` (rekonsiliasi penuh: mengisi,
memindah, dan mengosongkan). Setiap perubahan dicatat sebagai TiketAction
``DIUBAH`` atas nama user yang menekan tombol.

Alurnya sama seperti Generate Otomatis di halaman Durasi Jatuh Tempo: ringkasan
ditampilkan dulu (GET, tidak menulis apa pun), baru ditulis setelah user
menekan PROSES (POST).

Tambah/ubah/hapus lewat form sudah menyesuaikan tiket Sub Jenis Data-nya sendiri
(lihat ``utils/tiket_prioritas.py``). Tombol ini untuk seluruh tiket sekaligus —
tiket lama yang belum pernah diselaraskan, atau setelah record prioritas diubah
di luar form.
"""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from ..utils import tiket_prioritas

__all__ = [
    'jenis_prioritas_data_tiket_backfill_preview',
    'jenis_prioritas_data_tiket_backfill',
]

ADMIN_GROUPS = ['admin', 'admin_p3de', 'admin_pide', 'admin_pmde']
PREVIEW_LIMIT = 200


def _is_admin_any(user):
    return user.groups.filter(name__in=ADMIN_GROUPS).exists()


def _per_record(index, filled, relinked):
    rows = [
        {'record': index.label(pk), 'diisi': filled.get(pk, 0), 'dipindah': relinked.get(pk, 0)}
        for pk in set(filled) | set(relinked)
    ]
    rows.sort(key=lambda r: -(r['diisi'] + r['dipindah']))
    return rows


@login_required
@user_passes_test(_is_admin_any)
@require_GET
def jenis_prioritas_data_tiket_backfill_preview(request):
    """Ringkasan tiket yang akan disesuaikan FK prioritasnya. Side effects: None."""
    index = tiket_prioritas.build_index()
    changes, c = tiket_prioritas.rencana(index)
    per_record = _per_record(index, c['filled'], c['relinked'])
    return JsonResponse({
        'success': True,
        'total_tiket': len(changes),
        'diisi': sum(c['filled'].values()),
        'dipindah': sum(c['relinked'].values()),
        'dikosongkan': c['cleared'],
        'sudah_benar': c['already'],
        'bukan_prioritas': c['unmatched'],
        'total_record': len(index),
        'per_record': per_record[:PREVIEW_LIMIT],
        'per_record_sisa': max(len(per_record) - PREVIEW_LIMIT, 0),
    })


@login_required
@user_passes_test(_is_admin_any)
@require_POST
def jenis_prioritas_data_tiket_backfill(request):
    """Selaraskan ``Tiket.id_jenis_prioritas_data`` dengan aturan prioritas.

    Side effects: bulk update FK pada tiket yang berubah, plus satu TiketAction
    ``DIUBAH`` per tiket atas nama user yang menjalankan. Seluruhnya satu
    transaksi. Idempoten — menjalankan ulang tidak mengubah apa pun.
    """
    index = tiket_prioritas.build_index()
    changes, c = tiket_prioritas.rencana(index)

    if changes:
        with transaction.atomic():
            tiket_prioritas.terapkan(changes, index, request.user)

    if not changes:
        message = 'Semua tiket sudah sesuai Data Prioritas. Tidak ada yang diubah.'
    else:
        message = (
            f'{len(changes)} tiket disesuaikan: {sum(c["filled"].values())} diisi, '
            f'{sum(c["relinked"].values())} dipindah, {c["cleared"]} dikosongkan.'
        )
    return JsonResponse({'success': True, 'updated': len(changes), 'message': message})
