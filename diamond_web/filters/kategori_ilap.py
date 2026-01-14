import django_filters
from ..models.kategori_ilap import KategoriILAP

class KategoriILAPFilter(django_filters.FilterSet):
    nama_kategori = django_filters.CharFilter(lookup_expr='icontains', label='Search Nama Kategori')

    class Meta:
        model = KategoriILAP
        fields = ['nama_kategori']