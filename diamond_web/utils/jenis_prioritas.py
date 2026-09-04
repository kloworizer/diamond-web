"""Satu aturan penentuan Data Prioritas, dipakai seluruh aplikasi.

Sebuah tiket berstatus prioritas bila Sub Jenis Data ILAP-nya punya record
``JenisPrioritasData`` yang **masa berlakunya mencakup tanggal terima DIP tiket
itu**::

    start_date <= tgl_terima_dip <= end_date

Field ``tahun`` pada record prioritas **tidak** ikut menentukan. Itu tahun
penetapan prioritas (mengikuti Nota Dinas-nya), sedangkan ``Tiket.tahun`` adalah
tahun *isi data* — dua hal berbeda yang kebetulan sering sama. Data triwulan IV
2025 yang baru diterima Januari 2026 punya ``tahun`` 2025 tetapi diterima di
2026, jadi mencocokkan keduanya memberi jawaban yang salah. Sebelumnya form
Rekam Tiket dan sync memakai pencocokan tahun itu sementara antrean seksi memakai
rentang tanggal, sehingga satu tiket yang sama bisa tampil prioritas di satu menu
dan tidak di menu lain.

``end_date`` kosong berarti **masih berlaku sampai seterusnya**, sama seperti
yang diasumsikan validasi anti-tumpang-tindih pada form admin Data Prioritas.

Empat bentuk aturan yang sama disediakan di sini, supaya tidak ada penulis ulang:

* :func:`prioritas_window_q` — sebagai ``Q()``, untuk dipakai di dalam queryset.
* :func:`resolve_jenis_prioritas` — mengambil record-nya untuk satu tiket, dipakai
  saat menulis ``Tiket.id_jenis_prioritas_data``.
* :class:`PrioritasIndex` — seluruh tabel dimuat sekali, lalu dicocokkan di memori;
  untuk sync dan backfill yang menyapu puluhan ribu tiket sekaligus.
* :func:`is_prioritas_pada` — jawaban ya/tidak murni Python, untuk kode yang sudah
  memuat masa berlaku sendiri.
"""
from collections import defaultdict
from datetime import date, datetime

from django.db.models import Q

from ..models.jenis_prioritas_data import JenisPrioritasData


def as_tanggal(value):
    """Tanggal dari sebuah kolom datetime/date, atau None.

    ``tgl_terima_dip`` disimpan sebagai datetime tetapi masa berlaku prioritas
    dicatat per tanggal, jadi jamnya selalu dibuang lebih dulu.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def prioritas_window_q(tanggal):
    """``Q()`` yang cocok dengan record prioritas yang berlaku pada `tanggal`.

    `tanggal` boleh berupa tanggal biasa maupun ekspresi query (mis.
    ``Cast(OuterRef('tgl_terima_dip'), DateField())``) untuk subquery.
    """
    return (
        Q(start_date__lte=tanggal)
        & (Q(end_date__isnull=True) | Q(end_date__gte=tanggal))
    )


def resolve_jenis_prioritas(sub_jenis_data_ilap, tgl_terima_dip):
    """Record Data Prioritas yang berlaku untuk sebuah tiket, atau None.

    Args:
        sub_jenis_data_ilap: ``JenisDataILAP`` tiket (atau pk-nya).
        tgl_terima_dip: Tanggal terima DIP tiket.

    Form admin melarang rentang tanggal yang tumpang tindih untuk satu Sub Jenis
    Data, jadi pada data yang sehat hanya ada satu kandidat. Bila toh ada lebih
    dari satu, yang terlama (``id`` terkecil) yang dipakai — sama seperti
    ``.first()`` yang dipakai view lain saat menghadapi pilihan ganda.
    """
    tanggal = as_tanggal(tgl_terima_dip)
    if sub_jenis_data_ilap is None or tanggal is None:
        return None
    return (
        JenisPrioritasData.objects
        .filter(prioritas_window_q(tanggal), id_sub_jenis_data_ilap=sub_jenis_data_ilap)
        .order_by('id')
        .first()
    )


class PrioritasIndex:
    """Seluruh tabel Data Prioritas, siap dicocokkan tanpa query per tiket.

    Tabelnya kecil (satu record per Sub Jenis Data per penetapan) sedangkan
    tiketnya puluhan ribu, jadi seluruh isinya dimuat sekali di awal. Aturan
    pencocokannya sama persis dengan :func:`resolve_jenis_prioritas`, termasuk
    urutan ``id`` saat ada lebih dari satu kandidat.
    """

    def __init__(self, rows=None):
        if rows is None:
            rows = JenisPrioritasData.objects.select_related(
                'id_sub_jenis_data_ilap'
            ).order_by('id')
        self._by_sub = defaultdict(list)
        self._by_pk = {}
        for row in rows:
            self._by_sub[row.id_sub_jenis_data_ilap_id].append(row)
            self._by_pk[row.pk] = row

    def __len__(self):
        return len(self._by_pk)

    @property
    def sub_ids(self):
        """Sub Jenis Data ILAP yang punya penetapan prioritas."""
        return set(self._by_sub)

    def get(self, pk):
        return self._by_pk.get(pk)

    def subs_with(self, pks):
        """Sub Jenis Data ILAP yang memiliki salah satu record `pks`.

        Dipakai untuk mempersempit queryset tiket ketika hanya beberapa record
        prioritas yang sedang ditinjau.
        """
        pks = set(pks)
        return {
            sub_id
            for sub_id, rows in self._by_sub.items()
            if any(row.pk in pks for row in rows)
        }

    def label(self, pk):
        """Nama record untuk dilaporkan, mis. ``KM0330101 - 2025``."""
        if pk is None:
            return '-'
        row = self._by_pk.get(pk)
        return str(row) if row is not None else f'#{pk}'

    def match(self, sub_id, tgl_terima_dip):
        """Record prioritas yang berlaku untuk tiket itu, atau None."""
        tanggal = as_tanggal(tgl_terima_dip)
        if sub_id is None or tanggal is None:
            return None
        for row in self._by_sub.get(sub_id, ()):
            if not row.start_date or row.start_date > tanggal:
                continue
            if row.end_date and row.end_date < tanggal:
                continue
            return row
        return None

    def match_pk(self, sub_id, tgl_terima_dip):
        row = self.match(sub_id, tgl_terima_dip)
        return row.pk if row is not None else None


def is_prioritas_pada(windows, tgl_terima_dip):
    """Aturan yang sama, dijawab dari daftar ``(start_date, end_date)`` di memori.

    Dipakai kode yang sudah membaca seluruh masa berlaku sekaligus dan tidak
    boleh melakukan query per tiket.
    """
    tanggal = as_tanggal(tgl_terima_dip)
    if tanggal is None:
        return False
    return any(
        start_date and start_date <= tanggal and (end_date is None or end_date >= tanggal)
        for start_date, end_date in windows
    )
