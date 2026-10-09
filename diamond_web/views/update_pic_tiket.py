"""Menu Sinkronisasi Data > Update PIC Tiket.

Mengisi PIC P3DE/PIDE/PMDE pada tiket yang sama sekali tidak punya PIC untuk
role tersebut, diambil dari tabel PIC. Role yang sudah punya PIC — aktif maupun
nonaktif — tidak diubah.
Aturannya ada di ``utils/tiket_pic_backfill.py``.

Halaman (GET) hanya menampilkan preview — tidak menulis apa pun. Penulisan baru
terjadi setelah admin menekan PROSES (POST); rencana dihitung ulang saat itu,
sehingga yang ditulis selalu sesuai isi database terkini.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from ..utils import tiket_pic_backfill

__all__ = ['update_pic_tiket_page', 'update_pic_tiket_proses']


def _is_admin_user(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name='admin').exists()


@login_required
@user_passes_test(_is_admin_user)
@require_GET
def update_pic_tiket_page(request):
    """Preview PIC yang akan diisi. Side effects: None."""
    plan = tiket_pic_backfill.rencana()
    isi = plan['isi']
    rows = [
        {
            'nomor_tiket': item['nomor_tiket'],
            'id_tiket': item['id_tiket'],
            'status': item['status'],
            'sub_jenis_data': ' - '.join(filter(None, (item['id_sub_jenis_data'], item['nama_sub_jenis_data']))),
            'role': item['role_label'],
            'pic': [p['username'] for p in item['pic']],
        }
        for item in isi
    ]
    return render(request, 'update_pic_tiket/page.html', {
        'per_role': plan['per_role'],
        'total_celah': len(isi),
        'total_tiket': len({item['id_tiket'] for item in isi}),
        'total_pic': sum(len(item['pic']) for item in isi),
        'total_tanpa_sumber': sum(r['jumlah_tiket'] for r in plan['tanpa_sumber']),
        'tanpa_sumber': plan['tanpa_sumber'],
        'rows': rows,
    })


@login_required
@user_passes_test(_is_admin_user)
@require_POST
def update_pic_tiket_proses(request):
    """Isi PIC tiket yang kosong.

    Side effects: membuat ``TiketPIC`` baru dan satu
    ``TiketAction`` per PIC atas nama user yang menjalankan, dalam satu
    transaksi. Idempoten — menjalankan ulang tidak mengubah apa pun.
    """
    plan = tiket_pic_backfill.rencana()
    if not plan['isi']:
        messages.info(request, 'Tidak ada tiket yang perlu diisi PIC-nya.')
        return redirect('update_pic_tiket_page')

    with transaction.atomic():
        hasil = tiket_pic_backfill.terapkan(plan['isi'], request.user)

    messages.success(request, f"PIC diisi pada {hasil['tiket']} tiket: {hasil['dibuat']} PIC ditambahkan.")
    return redirect('update_pic_tiket_page')
