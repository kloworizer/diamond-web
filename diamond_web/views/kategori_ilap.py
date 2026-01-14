from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from ..models.kategori_ilap import KategoriILAP
from ..forms.kategori_ilap import KategoriILAPForm
from ..filters.kategori_ilap import KategoriILAPFilter
from ..tables.kategori_ilap import KategoriILAPTable

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name='Admin').exists()

class KategoriILAPListView(LoginRequiredMixin, AdminRequiredMixin, SingleTableMixin, FilterView):
    model = KategoriILAP
    table_class = KategoriILAPTable
    template_name = 'kategori_ilap/list.html'
    filterset_class = KategoriILAPFilter
    paginate_by = 10

class KategoriILAPCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = KategoriILAP
    form_class = KategoriILAPForm
    template_name = 'kategori_ilap/form.html'
    success_url = reverse_lazy('kategori_ilap_list')

class KategoriILAPUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = KategoriILAP
    form_class = KategoriILAPForm
    template_name = 'kategori_ilap/form.html'
    success_url = reverse_lazy('kategori_ilap_list')

class KategoriILAPDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = KategoriILAP
    template_name = 'kategori_ilap/confirm_delete.html'
    success_url = reverse_lazy('kategori_ilap_list')