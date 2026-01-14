import django_tables2 as tables
from ..models.ilap import ILAP


class ILAPTable(tables.Table):
    actions = tables.TemplateColumn(
        template_name="ilap/actions_column.html",
        verbose_name="Aksi",
        orderable=False
    )

    class Meta:
        model = ILAP
        template_name = "django_tables2/bootstrap5.html"
        fields = ("id_ilap", "id_kategori", "nama_ilap", "actions")
