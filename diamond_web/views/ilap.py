from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from ..models.ilap import ILAP
from ..forms.ilap import ILAPForm
from ..filters.ilap import ILAPFilter
from ..tables.ilap import ILAPTable


class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name='Admin').exists()


class ILAPListView(LoginRequiredMixin, AdminRequiredMixin, SingleTableMixin, FilterView):
    model = ILAP
    table_class = ILAPTable
    template_name = 'ilap/list.html'
    filterset_class = ILAPFilter
    paginate_by = 10

    def get(self, request, *args, **kwargs):
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'ILAP "{name}" deleted successfully.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


class ILAPCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = ILAP
    form_class = ILAPForm
    template_name = 'ilap/form.html'
    success_url = reverse_lazy('ilap_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'ILAP "{self.object}" created successfully.')
        return response


class ILAPUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = ILAP
    form_class = ILAPForm
    template_name = 'ilap/form.html'
    success_url = reverse_lazy('ilap_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'ILAP "{self.object}" updated successfully.')
        return response


class ILAPDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = ILAP
    template_name = 'ilap/confirm_delete.html'
    success_url = reverse_lazy('ilap_list')

    def get_success_url(self):
        obj = self.get_object()
        name = quote_plus(str(obj))
        return reverse('ilap_list') + f'?deleted=1&name={name}'
