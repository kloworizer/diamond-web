"""Isi PIC tiket yang kosong dari tabel PIC (menu Sinkronisasi Data > Update PIC Tiket).

Sebuah tiket "tidak punya PIC" untuk satu role (P3DE/PIDE/PMDE) bila tidak ada
satu pun baris ``TiketPIC`` untuk role itu — aktif maupun nonaktif. Celah seperti
ini muncul pada tiket migrasi.

Setiap celah (tiket, role) diisi dengan seluruh PIC aktif di tabel ``pic`` untuk
Sub Jenis Data tiket tersebut — aturan yang sama dengan saat tiket direkam
(``start_date <= hari ini`` dan ``end_date`` kosong). Role yang sudah punya baris
PIC tidak disentuh, termasuk bila seluruh barisnya nonaktif: PIC nonaktif berarti
seksi itu memang pernah punya PIC dan sengaja dilepas, jadi dibiarkan apa adanya.

``rencana()`` hanya membaca; ``terapkan()`` menulis hasil ``rencana()``.
"""
from collections import defaultdict
from datetime import datetime

from django.db.models import Exists, OuterRef

from ..constants.tiket_action_types import PICActionType
from ..constants.tiket_status import STATUS_LABELS
from ..models.pic import PIC
from ..models.tiket import Tiket
from ..models.tiket_action import TiketAction
from ..models.tiket_pic import TiketPIC

# (role TiketPIC, tipe PIC, label riwayat) — urutan tampilan di preview.
ROLES = (
    (TiketPIC.Role.P3DE, PIC.TipePIC.P3DE, 'PIC P3DE'),
    (TiketPIC.Role.PIDE, PIC.TipePIC.PIDE, 'PIC PIDE'),
    (TiketPIC.Role.PMDE, PIC.TipePIC.PMDE, 'PIC PMDE'),
)
ROLE_LABEL = {role: TiketPIC.Role(role).label for role, _, _ in ROLES}

def _tiket_tanpa_pic(role):
    """Tiket yang sama sekali tidak punya ``TiketPIC`` (aktif/nonaktif) untuk ``role``."""
    ada = TiketPIC.objects.filter(id_tiket=OuterRef('pk'), role=role)
    return (
        Tiket.objects
        .filter(~Exists(ada))
        .values(
            'id', 'nomor_tiket', 'status_tiket',
            'id_periode_data__id_sub_jenis_data_ilap',
            'id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data',
            'id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data',
            'id_periode_data__id_sub_jenis_data_ilap__nama_jenis_data',
        )
        .order_by('nomor_tiket')
    )


def _pic_aktif(today):
    """{(tipe, id sub jenis data): [(id_user, username), ...]} dari tabel PIC."""
    out = defaultdict(list)
    qs = (
        PIC.objects
        .filter(start_date__lte=today, end_date__isnull=True)
        .values_list('tipe', 'id_sub_jenis_data_ilap', 'id_user', 'id_user__username')
        .order_by('id')
    )
    for tipe, sub, user_id, username in qs:
        out[(tipe, sub)].append((user_id, username))
    return out


def _jumlah_pic_nonaktif(role):
    """Jumlah tiket yang punya baris ``TiketPIC`` untuk ``role`` tetapi tidak ada yang aktif.

    Tiket ini sengaja tidak diisi; dihitung hanya untuk ditampilkan di preview.
    """
    ada = TiketPIC.objects.filter(id_tiket=OuterRef('pk'), role=role)
    return Tiket.objects.filter(Exists(ada), ~Exists(ada.filter(active=True))).count()


def _nama_sub(row):
    # Sebagian Sub Jenis Data migrasi tidak punya nama; tampilkan nama Jenis Data-nya.
    return (
        row['id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data']
        or row['id_periode_data__id_sub_jenis_data_ilap__nama_jenis_data']
    )


def rencana(today=None):
    """Hitung apa yang akan diisi. Tidak menulis apa pun.

    Returns:
        dict dengan kunci:
        - ``isi``: list per celah (tiket, role) yang bisa diisi, masing-masing
          berisi data tiket dan ``pic`` = list ``{id_user, username}``.
        - ``tanpa_sumber``: list per (Sub Jenis Data, role) yang punya tiket
          tanpa PIC tetapi tidak ada PIC aktif di tabel PIC, plus jumlah tiketnya.
        - ``per_role``: ringkasan hitungan per role.
    """
    today = today or datetime.now().date()
    sumber = _pic_aktif(today)

    celah = []          # (role, row, pics)
    tanpa = defaultdict(int)
    tanpa_info = {}
    per_role = {
        role: {
            'role': role, 'label': ROLE_LABEL[role], 'tanpa_pic': 0, 'diisi': 0,
            'tanpa_sumber': 0, 'pic_nonaktif': _jumlah_pic_nonaktif(role),
        }
        for role, _, _ in ROLES
    }

    for role, tipe, _ in ROLES:
        for row in _tiket_tanpa_pic(role):
            sub = row['id_periode_data__id_sub_jenis_data_ilap']
            per_role[role]['tanpa_pic'] += 1
            pics = sumber.get((tipe, sub))
            if pics:
                per_role[role]['diisi'] += 1
                celah.append((role, row, pics))
            else:
                per_role[role]['tanpa_sumber'] += 1
                tanpa[(sub, role)] += 1
                tanpa_info[sub] = (
                    row['id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data'],
                    _nama_sub(row),
                )

    isi = []
    for role, row, pics in celah:
        isi.append({
            'id_tiket': row['id'],
            'nomor_tiket': row['nomor_tiket'],
            'status': STATUS_LABELS.get(row['status_tiket'], row['status_tiket']),
            'id_sub_jenis_data': row['id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data'],
            'nama_sub_jenis_data': _nama_sub(row),
            'role': role,
            'role_label': ROLE_LABEL[role],
            'pic': [{'id_user': user_id, 'username': username} for user_id, username in pics],
        })

    tanpa_sumber = sorted(
        (
            {
                'id_sub_jenis_data': tanpa_info[sub][0],
                'nama_sub_jenis_data': tanpa_info[sub][1],
                'role': role,
                'role_label': ROLE_LABEL[role],
                'jumlah_tiket': n,
            }
            for (sub, role), n in tanpa.items()
        ),
        key=lambda r: (-r['jumlah_tiket'], r['id_sub_jenis_data'], r['role']),
    )

    return {
        'isi': isi,
        'tanpa_sumber': tanpa_sumber,
        'per_role': [per_role[role] for role, _, _ in ROLES],
    }


def terapkan(isi, admin_user, now=None):
    """Tulis hasil ``rencana()['isi']``. Panggil di dalam ``transaction.atomic()``.

    Membuat ``TiketPIC`` baru plus satu ``TiketAction`` per PIC atas nama
    ``admin_user`` — sama seperti saat PIC ditambahkan lewat menu PIC.

    Returns:
        dict ``{'tiket': n tiket berbeda, 'dibuat': n baris TiketPIC baru}``.
    """
    now = now or datetime.now()
    tipe_label = {role: label for role, _, label in ROLES}
    baru, aksi = [], []

    for item in isi:
        label = tipe_label[item['role']]
        for pic in item['pic']:
            baru.append(TiketPIC(
                id_tiket_id=item['id_tiket'],
                id_user_id=pic['id_user'],
                role=item['role'],
                active=True,
                timestamp=now,
            ))
            aksi.append(TiketAction(
                id_tiket_id=item['id_tiket'],
                id_user=admin_user,
                timestamp=now,
                action=PICActionType.DITAMBAHKAN,
                catatan=f"{label} {pic['username']} ditambahkan",
            ))

    TiketPIC.objects.bulk_create(baru, batch_size=500)
    TiketAction.objects.bulk_create(aksi, batch_size=500)

    return {
        'tiket': len({item['id_tiket'] for item in isi}),
        'dibuat': len(baru),
    }
