from datetime import datetime
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.backup_data import BackupData
from ..models.tiket import Tiket
from ..models.tiket_action import TiketAction
from ..forms.backup_data import BackupDataForm
from .mixins import AjaxFormMixin, UserP3DERequiredMixin


def create_tiket_action(tiket, user, catatan):
    if not tiket:
        return
    TiketAction.objects.create(
        id_tiket=tiket,
        id_user=user,
        timestamp=datetime.now(),
        action=tiket.status,
        catatan=catatan
    )

class BackupDataListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView):
    template_name = 'backup_data/list.html'

class BackupDataCreateView(LoginRequiredMixin, UserP3DERequiredMixin, AjaxFormMixin, CreateView):
    model = BackupData
    form_class = BackupDataForm
    template_name = 'backup_data/form.html'
    success_url = reverse_lazy('backup_data_list')
    success_message = 'Data Backup berhasil direkam.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('backup_data_create')
        context['page_title'] = 'Rekam Backup Data'
        return context

    def form_valid(self, form):
        form.instance.id_user = self.request.user
        response = super().form_valid(form)
        create_tiket_action(self.object.id_tiket, self.request.user, "backup data direkam")
        return response

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

class BackupDataFromTiketCreateView(LoginRequiredMixin, UserP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create Backup Data from a specific Tiket."""
    model = BackupData
    form_class = BackupDataForm
    template_name = 'backup_data/form.html'
    success_message = 'Data Backup berhasil direkam.'

    def get_success_url(self):
        return reverse('tiket_detail', kwargs={'pk': self.kwargs['tiket_pk']})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tiket_pk'] = self.kwargs.get('tiket_pk')
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('backup_data_from_tiket_create', kwargs={'tiket_pk': self.kwargs['tiket_pk']})
        context['page_title'] = f'Rekam Backup Data'
        context['tiket'] = Tiket.objects.get(pk=self.kwargs['tiket_pk'])
        return context

    def form_valid(self, form):
        form.instance.id_user = self.request.user
        # Set the tiket from the tiket_pk
        tiket = Tiket.objects.get(pk=self.kwargs['tiket_pk'])
        form.instance.id_tiket = tiket
        self.object = form.save()
        
        # Update tiket status to 2 (Backup direkam)
        tiket.status = 2
        tiket.save()
        
        # Record tiket_action for audit trail
        TiketAction.objects.create(
            id_tiket=tiket,
            id_user=self.request.user,
            timestamp=datetime.now(),
            action=2,
            catatan="backup data direkam"
        )
        
        return AjaxFormMixin.form_valid(self, form)

class BackupDataUpdateView(LoginRequiredMixin, UserP3DERequiredMixin, AjaxFormMixin, UpdateView):
    model = BackupData
    form_class = BackupDataForm
    template_name = 'backup_data/form.html'
    success_url = reverse_lazy('backup_data_list')
    success_message = 'Data Backup berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('backup_data_update', args=[self.object.pk])
        context['page_title'] = 'Edit Data Backup'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        create_tiket_action(self.object.id_tiket, self.request.user, "backup data diperbarui")
        return response

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)


class BackupDataDeleteView(LoginRequiredMixin, UserP3DERequiredMixin, DeleteView):
    model = BackupData
    template_name = 'backup_data/confirm_delete.html'
    success_url = reverse_lazy('backup_data_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('backup_data_delete', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Data Backup berhasil dihapus.'
            })
        messages.success(request, 'Data Backup berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def backup_data_data(request):
    """Server-side processing for DataTables."""
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = BackupData.objects.select_related('id_user', 'id_tiket').all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # No Tiket
            qs = qs.filter(id_tiket__nomor_tiket__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Lokasi Backup
            qs = qs.filter(lokasi_backup__icontains=columns_search[1])

    records_filtered = qs.count()

    # Ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_tiket__nomor_tiket', 'lokasi_backup', 'id_user__username']
    
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'id'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('-created_at')
    else:
        qs = qs.order_by('-created_at')

    qs_page = qs[start:start + length]

    data = []
    for obj in qs_page:
        user_name = obj.id_user.username if obj.id_user else '-'
        
        data.append({
            'no_tiket': obj.id_tiket.nomor_tiket if obj.id_tiket else '-',
            'lokasi_backup': obj.lokasi_backup,
            'user': user_name,
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('backup_data_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('backup_data_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })