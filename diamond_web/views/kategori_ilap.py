from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
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

    def get(self, request, *args, **kwargs):
        # If redirected after delete, show success message from query params
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Kategori "{name}" deleted successfully.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class KategoriILAPCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = KategoriILAP
    form_class = KategoriILAPForm
    template_name = 'kategori_ilap/form.html'
    success_url = reverse_lazy('kategori_ilap_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Kategori "{self.object}" created successfully.')
        return response

class KategoriILAPUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = KategoriILAP
    form_class = KategoriILAPForm
    template_name = 'kategori_ilap/form.html'
    success_url = reverse_lazy('kategori_ilap_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Kategori "{self.object}" updated successfully.')
        return response

class KategoriILAPDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = KategoriILAP
    template_name = 'kategori_ilap/confirm_delete.html'
    success_url = reverse_lazy('kategori_ilap_list')

    def get_success_url(self):
        # include deleted object's name in query params so the list view can show a message
        obj = self.get_object()
        name = quote_plus(str(obj))
        return reverse('kategori_ilap_list') + f'?deleted=1&name={name}'