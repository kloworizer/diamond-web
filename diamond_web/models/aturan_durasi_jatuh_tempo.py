from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import Group

from .audit import AuditTrailModel
from .ilap import ILAP
from .jenis_data_ilap import JenisDataILAP


class AturanDurasiJatuhTempo(AuditTrailModel):
    """Berapa hari durasi jatuh tempo suatu seksi untuk satu tahun.

    Ini sumber angka yang dipakai tombol **Generate Otomatis** dan **Sinkronkan
    Prioritas** pada menu Durasi Jatuh Tempo — menggantikan konstanta yang dulu
    tertanam di kode (``GENERATE_PMDE_DURASI_PRIORITAS = 45`` dan kawan-kawan).
    Baris ``DurasiJatuhTempo`` yang dihasilkan tetap jadi tempat penyimpanan
    sebenarnya; tabel ini hanya menyimpan aturannya, supaya bisa diubah lewat UI
    dan tercatat siapa mengubah kapan.

    Dua sumbu yang harus ditampung sekaligus:

    * **Per tahun.** Durasi prioritas PMDE 45 hari di 2026 bisa jadi 35 di 2027.
    * **Per ILAP / per sub jenis data.** Data Direktorat Jenderal Bea dan Cukai
      berdurasi 14 hari ketika prioritas, bukan 45 seperti ILAP lain.

    Karena itu ``id_ilap`` dan ``id_sub_jenis_data`` keduanya opsional, dan
    **yang paling spesifik menang**: aturan untuk satu sub jenis data
    mengalahkan aturan untuk ILAP-nya, yang mengalahkan aturan umum tahun itu.
    Lihat :meth:`resolve`.
    """

    # Urutan pencarian aturan, dari yang paling khusus ke yang paling umum.
    SPECIFICITY_SUB_JENIS = 2
    SPECIFICITY_ILAP = 1
    SPECIFICITY_UMUM = 0

    id = models.AutoField(primary_key=True, verbose_name="ID")
    seksi = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        db_column="seksi",
        verbose_name="Seksi",
        help_text="Grup seksi pemilik aturan, mis. user_pide atau user_pmde.",
    )
    tahun = models.IntegerField(verbose_name="Tahun")
    durasi_prioritas = models.IntegerField(
        verbose_name="Durasi Prioritas",
        help_text="Hari jatuh tempo bila data berstatus prioritas pada tahun itu.",
    )
    durasi_non_prioritas = models.IntegerField(
        verbose_name="Durasi Non Prioritas",
        help_text="Hari jatuh tempo bila data tidak berstatus prioritas.",
    )
    id_ilap = models.ForeignKey(
        ILAP,
        on_delete=models.PROTECT,
        db_column="id_ilap",
        null=True,
        blank=True,
        verbose_name="ILAP",
        help_text="Kosongkan untuk aturan umum. Diisi bila satu ILAP punya durasi sendiri.",
    )
    id_sub_jenis_data = models.ForeignKey(
        JenisDataILAP,
        on_delete=models.PROTECT,
        db_column="id_sub_jenis_data",
        null=True,
        blank=True,
        verbose_name="Sub Jenis Data ILAP",
        help_text="Kosongkan kecuali satu sub jenis data perlu durasi berbeda dari ILAP-nya.",
    )

    class Meta:
        verbose_name = "Aturan Durasi Jatuh Tempo"
        verbose_name_plural = "Aturan Durasi Jatuh Tempo"
        db_table = "aturan_durasi_jatuh_tempo"
        ordering = ["seksi", "tahun", "id_ilap", "id_sub_jenis_data"]
        indexes = [
            # Melayani resolve(): seluruh aturan satu seksi untuk satu tahun
            # dibaca sekaligus, lalu dipilih yang paling spesifik.
            models.Index(fields=["seksi", "tahun"], name="adjt_seksi_tahun_idx"),
        ]
        constraints = [
            # NULL tidak pernah sama dengan NULL di UniqueConstraint biasa,
            # jadi tiap tingkat kekhususan dijaga constraint terpisah dengan
            # condition — kalau tidak, aturan umum untuk (seksi, tahun) bisa
            # diinput dua kali tanpa penolakan.
            models.UniqueConstraint(
                fields=["seksi", "tahun"],
                condition=models.Q(id_ilap__isnull=True, id_sub_jenis_data__isnull=True),
                name="unique_aturan_durasi_umum",
            ),
            models.UniqueConstraint(
                fields=["seksi", "tahun", "id_ilap"],
                condition=models.Q(id_ilap__isnull=False, id_sub_jenis_data__isnull=True),
                name="unique_aturan_durasi_ilap",
            ),
            models.UniqueConstraint(
                fields=["seksi", "tahun", "id_sub_jenis_data"],
                condition=models.Q(id_sub_jenis_data__isnull=False),
                name="unique_aturan_durasi_sub_jenis",
            ),
        ]

    def __str__(self):
        cakupan = self.cakupan
        return f"{self.seksi} {self.tahun} — {cakupan}"

    @property
    def cakupan(self):
        """Sebutan cakupan aturan ini, untuk ditampilkan di tabel dan pesan."""
        if self.id_sub_jenis_data_id:
            return str(self.id_sub_jenis_data)
        if self.id_ilap_id:
            return str(self.id_ilap)
        return "Semua ILAP"

    @property
    def specificity(self):
        if self.id_sub_jenis_data_id:
            return self.SPECIFICITY_SUB_JENIS
        if self.id_ilap_id:
            return self.SPECIFICITY_ILAP
        return self.SPECIFICITY_UMUM

    def clean(self):
        """Sub jenis data yang diisi harus benar-benar milik ILAP yang diisi.

        Tanpa ini sebuah aturan bisa menyebut pasangan yang tidak berhubungan,
        dan pencocokannya jadi tidak bisa dijelaskan.
        """
        if (
            self.id_sub_jenis_data_id
            and self.id_ilap_id
            and self.id_sub_jenis_data.id_ilap_id != self.id_ilap_id
        ):
            raise ValidationError({
                'id_sub_jenis_data': (
                    f'Sub Jenis Data "{self.id_sub_jenis_data}" bukan milik ILAP '
                    f'"{self.id_ilap}".'
                )
            })

    @classmethod
    def resolve(cls, aturan, sub_jenis_data_id, ilap_id, tahun, is_prioritas):
        """Durasi yang berlaku untuk satu sub jenis data pada satu tahun.

        Args:
            aturan: Hasil :meth:`index_for`, seluruh aturan satu seksi.
            sub_jenis_data_id: pk JenisDataILAP.
            ilap_id: pk ILAP pemilik sub jenis data itu.
            tahun: Tahun yang dinilai.
            is_prioritas: Apakah data berstatus prioritas pada tahun itu.

        Returns:
            int durasi, atau None bila tahun itu belum punya aturan sama sekali.
            Pemanggil yang memutuskan apa artinya — generate melewatinya dan
            melaporkannya, bukan menebak angka.
        """
        for key in (
            (tahun, cls.SPECIFICITY_SUB_JENIS, sub_jenis_data_id),
            (tahun, cls.SPECIFICITY_ILAP, ilap_id),
            (tahun, cls.SPECIFICITY_UMUM, None),
        ):
            row = aturan.get(key)
            if row is not None:
                return row[0] if is_prioritas else row[1]
        return None

    @classmethod
    def index_for(cls, seksi):
        """Seluruh aturan satu seksi sebagai ``{(tahun, kekhususan, ref): (prio, non)}``.

        Dibaca sekali di awal supaya generate yang menyapu belasan ribu sub jenis
        data tidak melakukan query per baris.
        """
        index = {}
        for row in cls.objects.filter(seksi=seksi):
            if row.id_sub_jenis_data_id:
                key = (row.tahun, cls.SPECIFICITY_SUB_JENIS, row.id_sub_jenis_data_id)
            elif row.id_ilap_id:
                key = (row.tahun, cls.SPECIFICITY_ILAP, row.id_ilap_id)
            else:
                key = (row.tahun, cls.SPECIFICITY_UMUM, None)
            index[key] = (row.durasi_prioritas, row.durasi_non_prioritas)
        return index

    @classmethod
    def tahun_tersedia(cls, seksi):
        """Tahun-tahun yang punya aturan umum untuk seksi ini, terurut."""
        return sorted(
            cls.objects.filter(
                seksi=seksi, id_ilap__isnull=True, id_sub_jenis_data__isnull=True
            ).values_list('tahun', flat=True)
        )
