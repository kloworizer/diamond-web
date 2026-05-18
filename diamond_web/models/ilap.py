from django.db import models
from django.db.models import UniqueConstraint
from .kategori_ilap import KategoriILAP
from .kpp import KPP
from .kategori_wilayah import KategoriWilayah

class ILAP(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_ilap = models.CharField(max_length=5, verbose_name="ID ILAP")
    id_kategori = models.ForeignKey(
        KategoriILAP,
        on_delete=models.PROTECT,
        db_column="id_kategori",
        verbose_name="ID Kategori"
    )
    nama_ilap = models.CharField(max_length=150, verbose_name="Nama ILAP")
    id_kategori_wilayah = models.ForeignKey(
        KategoriWilayah,
        on_delete=models.PROTECT,
        db_column="id_kategori_wilayah",
        verbose_name="Kategori Wilayah"
    )
    id_kpp = models.ForeignKey(
        KPP,
        on_delete=models.PROTECT,
        db_column="id_kpp",
        verbose_name="KPP",
        null=True,
        blank=True
    )
    alamat_ilap = models.CharField(max_length=3000, null=True, blank=True, verbose_name="Alamat ILAP")
    kota_ilap = models.CharField(max_length=30, null=True, blank=True, verbose_name="Kota ILAP")
    namapic_ilap = models.CharField(max_length=100, null=True, blank=True, verbose_name="Nama PIC ILAP")
    telp_kantor = models.CharField(max_length=100, null=True, blank=True, verbose_name="Telp Kantor")
    fax_ilap = models.CharField(max_length=100, null=True, blank=True, verbose_name="Fax ILAP")
    email_picilap = models.CharField(max_length=100, null=True, blank=True, verbose_name="Email PIC ILAP")
    create_date = models.DateField(null=True, blank=True, verbose_name="Create Date")
    create_by = models.CharField(max_length=9, null=True, blank=True, verbose_name="Create By")
    jabatan_picilap = models.CharField(max_length=100, null=True, blank=True, verbose_name="Jabatan PIC ILAP")
    telp_pic = models.CharField(max_length=100, null=True, blank=True, verbose_name="Telp PIC")
    tujuan_surat = models.CharField(max_length=200, null=True, blank=True, verbose_name="Tujuan Surat")
    tembusan = models.CharField(max_length=200, null=True, blank=True, verbose_name="Tembusan")
    update_date = models.DateField(null=True, blank=True, verbose_name="Update Date")
    update_by = models.CharField(max_length=9, null=True, blank=True, verbose_name="Update By")

    class Meta:
        verbose_name = "ILAP"
        verbose_name_plural = "ILAP"
        db_table = "ilap"
        ordering = ["id_ilap"]
        constraints = [
            UniqueConstraint(fields=["id_ilap", "nama_ilap"], name="unique_ilap_id_nama"),
        ]

    def __str__(self):
        return f"{self.id_ilap} - {self.nama_ilap}"