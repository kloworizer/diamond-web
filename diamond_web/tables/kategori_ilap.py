import django_tables2 as tables
from ..models.kategori_ilap import KategoriILAP

class KategoriILAPTable(tables.Table):
    actions = tables.TemplateColumn(
        template_name="kategori_ilap/actions_column.html",
        verbose_name="Aksi",
        orderable=False
    )

    class Meta:
        model = KategoriILAP
        template_name = "django_tables2/bootstrap5.html"
        fields = ("id_kategori", "nama_kategori", "actions")