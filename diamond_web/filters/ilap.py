import django_filters
from ..models.ilap import ILAP


class ILAPFilter(django_filters.FilterSet):
    nama_ilap = django_filters.CharFilter(lookup_expr='icontains', label='Search Nama ILAP')

    class Meta:
        model = ILAP
        fields = ['nama_ilap']
