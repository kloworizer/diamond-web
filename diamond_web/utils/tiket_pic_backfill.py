"""Isi PIC tiket yang kosong dari tabel PIC (menu Sinkronisasi Data > Update PIC Tiket).

Sebuah tiket "tidak punya PIC aktif" untuk satu role (P3DE/PIDE/PMDE) bila tidak
ada satu pun baris ``TiketPIC`` aktif untuk role itu. Celah seperti ini muncul
pada tiket migrasi dan pada tiket yang PIC-nya diakhiri tanpa pengganti.

Setiap celah (tiket, role) diisi dengan seluruh PIC aktif di tabel ``pic`` untuk
Sub Jenis Data tiket tersebut — aturan yang sama dengan saat tiket direkam
(``start_date <= hari ini`` dan ``end_date`` kosong). Role yang sudah punya PIC
aktif tidak disentuh sama sekali. Bila user tersebut pernah menjadi PIC role itu
di tiket yang sama (barisnya nonaktif), baris lama diaktifkan kembali alih-alih
membuat baris ganda.

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

# SQLite membatasi jumlah parameter per query; potong daftar id tiket.
_CHUNK = 900


def _chunks(items, size=_CHUNK):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _tiket_tanpa_pic(role):
    """Tiket yang tidak punya ``TiketPIC`` aktif untuk ``role``."""
    aktif = TiketPIC.objects.filter(id_tiket=OuterRef('pk'), role=role, active=True)
    return (
        Tiket.objects
        .filter(~Exists(aktif))
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


def _baris_nonaktif(tiket_ids):
    """{(id_tiket, id_user, role): id TiketPIC} untuk baris nonaktif yang bisa dipakai ulang."""
    out = {}
    for chunk in _chunks(tiket_ids):
        qs = (
            TiketPIC.objects
            .filter(id_tiket__in=chunk, active=False)
            .values_list('id', 'id_tiket', 'id_user', 'role')
            .order_by('id')
        )
        for pk, tiket_id, user_id, role in qs:
            out.setdefault((tiket_id, user_id, role), pk)
    return out


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
          berisi data tiket dan ``pic`` = list ``{id_user, username, id_tiket_pic}``
          (``id_tiket_pic`` terisi bila baris lama akan diaktifkan kembali).
        - ``tanpa_sumber``: list per (Sub Jenis Data, role) yang punya tiket
          tanpa PIC aktif tetapi tidak ada PIC aktif di tabel PIC, plus jumlah tiketnya.
        - ``per_role``: ringkasan hitungan per role.
    """
    today = today or datetime.now().date()
    sumber = _pic_aktif(today)

    celah = []          # (role, tipe, row, pics)
    tanpa = defaultdict(int)
    tanpa_info = {}
    per_role = {
        role: {'role': role, 'label': ROLE_LABEL[role], 'tanpa_pic': 0, 'diisi': 0, 'tanpa_sumber': 0}
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

    nonaktif = _baris_nonaktif({row['id'] for _, row, _ in celah})

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
            'pic': [
                {
                    'id_user': user_id,
                    'username': username,
                    'id_tiket_pic': nonaktif.get((row['id'], user_id, role)),
                }
                for user_id, username in pics
            ],
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

    Membuat ``TiketPIC`` baru atau mengaktifkan kembali baris lama, plus satu
    ``TiketAction`` per PIC atas nama ``admin_user`` — sama seperti saat PIC
    ditambahkan lewat menu PIC.

    Returns:
        dict ``{'tiket': n tiket berbeda, 'dibuat': n baris baru, 'diaktifkan': n baris diaktifkan kembali}``.
    """
    now = now or datetime.now()
    tipe_label = {role: label for role, _, label in ROLES}
    baru, aktifkan, aksi = [], [], []

    for item in isi:
        for pic in item['pic']:
            label = tipe_label[item['role']]
            if pic['id_tiket_pic']:
                aktifkan.append(pic['id_tiket_pic'])
                action = PICActionType.DIAKTIFKAN_KEMBALI
                catatan = f"{label} {pic['username']} diaktifkan kembali"
            else:
                baru.append(TiketPIC(
                    id_tiket_id=item['id_tiket'],
                    id_user_id=pic['id_user'],
                    role=item['role'],
                    active=True,
                    timestamp=now,
                ))
                action = PICActionType.DITAMBAHKAN
                catatan = f"{label} {pic['username']} ditambahkan"
            aksi.append(TiketAction(
                id_tiket_id=item['id_tiket'],
                id_user=admin_user,
                timestamp=now,
                action=action,
                catatan=catatan,
            ))

    TiketPIC.objects.bulk_create(baru, batch_size=500)
    for chunk in _chunks(aktifkan):
        TiketPIC.objects.filter(id__in=chunk).update(active=True)
    TiketAction.objects.bulk_create(aksi, batch_size=500)

    return {
        'tiket': len({item['id_tiket'] for item in isi}),
        'dibuat': len(baru),
        'diaktifkan': len(aktifkan),
    }
