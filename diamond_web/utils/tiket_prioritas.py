"""Menyelaraskan ``Tiket.id_jenis_prioritas_data`` dengan tabel Data Prioritas.

Aturannya ada di :mod:`diamond_web.utils.jenis_prioritas`: tiket prioritas bila
masa berlaku record Data Prioritas untuk Sub Jenis Data-nya mencakup tanggal
terima DIP tiket. Modul ini yang **menulis** hasilnya ke kolom FK tiket, dipakai:

* form tambah/ubah/hapus Data Prioritas — hanya tiket dari Sub Jenis Data yang
  disentuh, dalam transaksi yang sama dengan perubahan record-nya;
* tombol Sinkronisasi Prioritas langkah 2 — seluruh tiket.

Setiap tiket yang berubah dicatat sebagai TiketAction ``DIUBAH`` bertanda
``(penyesuaian jenis prioritas data)``, sama seperti perintah
``backfill_tiket_jenis_prioritas``.
"""
from collections import Counter
from datetime import datetime

from ..constants.tiket_action_types import TiketActionType
from ..models.jenis_prioritas_data import JenisPrioritasData
from ..models.tiket import Tiket
from ..models.tiket_action import TiketAction
from .jenis_prioritas import PrioritasIndex

SUB_FIELD = 'id_periode_data__id_sub_jenis_data_ilap'
TIKET_FIELDS = ('id', 'tgl_terima_dip', 'id_jenis_prioritas_data', SUB_FIELD)
BATCH_SIZE = 2000


def build_index(exclude_pk=None):
    """Seluruh tabel Data Prioritas; `exclude_pk` untuk record yang akan dihapus."""
    rows = JenisPrioritasData.objects.select_related('id_sub_jenis_data_ilap').order_by('id')
    if exclude_pk is not None:
        rows = rows.exclude(pk=exclude_pk)
    return PrioritasIndex(rows)


def sub_terkait(record):
    """Sub Jenis Data yang tiketnya perlu dinilai ulang saat `record` berubah.

    Sub Jenis Data record itu sendiri, ditambah Sub Jenis Data setiap tiket yang
    sekarang menunjuknya — data lama tidak selalu konsisten, dan tiket seperti
    itu harus ikut dilepas supaya FK PROTECT tidak menahan penghapusan.
    """
    subs = set(
        Tiket.objects.filter(id_jenis_prioritas_data=record.pk)
        .values_list(SUB_FIELD, flat=True)
        .distinct()
    )
    subs.add(record.id_sub_jenis_data_ilap_id)
    return subs


def rencana(index, sub_ids=None):
    """Tiket yang FK prioritasnya belum sesuai `index`.

    Args:
        index: :class:`PrioritasIndex` yang menjadi acuan.
        sub_ids: batasi ke Sub Jenis Data ILAP (pk) ini; None = seluruh tiket.

    Returns ``(changes, counters)`` — ``changes`` berisi
    ``(tiket_id, lama, baru)``; ``counters`` berisi ``filled`` dan
    ``relinked`` (Counter per record baru), ``cleared``, ``already`` dan
    ``unmatched``.
    """
    changes = []
    filled = Counter()
    relinked = Counter()
    cleared = already = unmatched = 0

    tikets = Tiket.objects.order_by('id')
    if sub_ids is not None:
        tikets = tikets.filter(**{f'{SUB_FIELD}__in': [s for s in sub_ids if s is not None]})

    for t in tikets.values(*TIKET_FIELDS).iterator(chunk_size=BATCH_SIZE):
        current = t['id_jenis_prioritas_data']
        wanted = index.match_pk(t[SUB_FIELD], t['tgl_terima_dip'])
        if wanted == current:
            if current is None:
                unmatched += 1
            else:
                already += 1
            continue
        if current is None:
            filled[wanted] += 1
        elif wanted is None:
            cleared += 1
        else:
            relinked[wanted] += 1
        changes.append((t['id'], current, wanted))

    return changes, {
        'filled': filled,
        'relinked': relinked,
        'cleared': cleared,
        'already': already,
        'unmatched': unmatched,
    }


def terapkan(changes, index, user):
    """Tulis `changes` ke tiket plus satu TiketAction per tiket atas nama `user`.

    Tidak membuka transaksi sendiri — pemanggil yang menentukan batasnya.
    """
    # Diimpor di sini: modul command ikut memuat model & BaseCommand, cukup
    # untuk pesan riwayatnya saja.
    from ..management.commands.backfill_tiket_jenis_prioritas import build_catatan

    now = datetime.now()
    for start in range(0, len(changes), BATCH_SIZE):
        batch = changes[start:start + BATCH_SIZE]
        Tiket.objects.bulk_update(
            [Tiket(pk=tiket_id, id_jenis_prioritas_data_id=baru) for tiket_id, _lama, baru in batch],
            ['id_jenis_prioritas_data'],
        )
        TiketAction.objects.bulk_create([
            TiketAction(
                id_tiket_id=tiket_id,
                id_user=user,
                timestamp=now,
                action=TiketActionType.DIUBAH,
                catatan=build_catatan(index.label(lama), index.label(baru)),
            )
            for tiket_id, lama, baru in batch
        ])


def selaraskan(user, sub_ids=None, exclude_pk=None):
    """Hitung lalu tulis penyesuaian; kembalikan ringkasan jumlahnya.

    Returns dict ``jadi_prioritas`` (FK kosong -> terisi), ``dipindah``
    (pindah ke record lain) dan ``tidak_prioritas`` (terisi -> kosong).
    """
    index = build_index(exclude_pk=exclude_pk)
    changes, c = rencana(index, sub_ids=sub_ids)
    if changes:
        terapkan(changes, index, user)
    return {
        'jadi_prioritas': sum(c['filled'].values()),
        'dipindah': sum(c['relinked'].values()),
        'tidak_prioritas': c['cleared'],
    }


def ringkasan(hasil):
    """Kalimat singkat untuk toast, mis. "98 tiket menjadi prioritas."."""
    bagian = []
    if hasil['jadi_prioritas']:
        bagian.append(f"{hasil['jadi_prioritas']} tiket menjadi prioritas")
    if hasil['tidak_prioritas']:
        bagian.append(f"{hasil['tidak_prioritas']} tiket tidak lagi prioritas")
    if hasil['dipindah']:
        bagian.append(f"{hasil['dipindah']} tiket dipindah ke Data Prioritas lain")
    if not bagian:
        return 'Tidak ada status prioritas tiket yang berubah.'
    return ', '.join(bagian) + '.'
