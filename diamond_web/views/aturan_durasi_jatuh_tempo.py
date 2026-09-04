"""Menu Aturan Durasi Jatuh Tempo — sumber angka Generate Otomatis.

Tabel ini yang menentukan berapa hari durasi jatuh tempo dipakai Generate
Otomatis dan Sinkronkan Prioritas pada menu Durasi Jatuh Tempo PIDE dan PMDE.
Sebelumnya angkanya konstanta di ``views/durasi_jatuh_tempo.py``, sehingga
mengubah durasi prioritas dari 45 ke 35 menuntut ubah kode dan deploy ulang.

Dikelola bersama PIDE dan PMDE — masing-masing mengurus barisnya sendiri,
tetapi keduanya melihat tabel yang sama supaya aturan antar seksi bisa
dibandingkan sekilas.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView
from urllib.parse import unquote_plus

from ..forms.aturan_durasi_jatuh_tempo import SEKSI_LABELS, AturanDurasiJatuhTempoForm
from ..models.aturan_durasi_jatuh_tempo import AturanDurasiJatuhTempo
from .mixins import AjaxFormMixin, SafeDeleteMixin

ADMIN_GROUPS = ['admin', 'admin_pide', 'admin_pmde']


class AdminDurasiRequiredMixin(UserPassesTestMixin):
    """Admin global, PIDE, atau PMDE — ketiganya mengelola tabel ini bersama."""
    raise_exception = True

    def test_func(self):
        return self.request.user.groups.filter(name__in=ADMIN_GROUPS).exists()


class AturanDurasiJatuhTempoListView(
    LoginRequiredMixin, AdminDurasiRequiredMixin, TemplateView
):
    template_name = 'aturan_durasi_jatuh_tempo/list.html'

    def get(self, request, *args, **kwargs):
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                messages.success(
                    request, f'Aturan Durasi Jatuh Tempo "{unquote_plus(name)}" berhasil dihapus.'
                )
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


class AturanDurasiJatuhTempoCreateView(
    LoginRequiredMixin, AdminDurasiRequiredMixin, AjaxFormMixin, CreateView
):
    model = AturanDurasiJatuhTempo
    form_class = AturanDurasiJatuhTempoForm
    template_name = 'aturan_durasi_jatuh_tempo/form.html'
    success_url = reverse_lazy('aturan_durasi_jatuh_tempo_list')
    success_message = 'Aturan Durasi Jatuh Tempo "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('aturan_durasi_jatuh_tempo_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        return self.render_form_response(self.get_form())

    def form_valid(self, form):
        today = timezone.now().date()
        username = (getattr(self.request.user, 'username', '') or '')[:9]
        form.instance.create_date = today
        form.instance.create_by = username
        form.instance.update_date = today
        form.instance.update_by = username
        return super().form_valid(form)


class AturanDurasiJatuhTempoUpdateView(
    LoginRequiredMixin, AdminDurasiRequiredMixin, AjaxFormMixin, UpdateView
):
    model = AturanDurasiJatuhTempo
    form_class = AturanDurasiJatuhTempoForm
    template_name = 'aturan_durasi_jatuh_tempo/form.html'
    success_url = reverse_lazy('aturan_durasi_jatuh_tempo_list')
    success_message = 'Aturan Durasi Jatuh Tempo "{object}" berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse(
            'aturan_durasi_jatuh_tempo_update', args=[self.object.pk]
        )
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_form_response(self.get_form())

    def form_valid(self, form):
        form.instance.update_date = timezone.now().date()
        form.instance.update_by = (getattr(self.request.user, 'username', '') or '')[:9]
        return super().form_valid(form)


class AturanDurasiJatuhTempoDeleteView(
    SafeDeleteMixin, LoginRequiredMixin, AdminDurasiRequiredMixin, DeleteView
):
    """Hapus satu aturan.

    Menghapus aturan tidak mengubah baris ``DurasiJatuhTempo`` yang terlanjur
    dibuat darinya — angka yang sudah tertulis tetap berlaku sampai
    Sinkronkan Prioritas dijalankan lagi.
    """
    model = AturanDurasiJatuhTempo
    template_name = 'aturan_durasi_jatuh_tempo/confirm_delete.html'
    success_url = reverse_lazy('aturan_durasi_jatuh_tempo_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse(
            'aturan_durasi_jatuh_tempo_delete', args=[self.object.pk]
        )
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(
                self.template_name, self.get_context_data(object=self.object), request=request
            )
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=ADMIN_GROUPS).exists())
@require_GET
def aturan_durasi_jatuh_tempo_data(request):
    """Endpoint DataTables server-side untuk tabel aturan."""
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = AturanDurasiJatuhTempo.objects.select_related(
        'seksi', 'id_ilap', 'id_sub_jenis_data'
    )
    records_total = qs.count()

    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:
            qs = qs.filter(seksi__name__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:
            qs = qs.filter(tahun__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:
            nilai = columns_search[2]
            qs = qs.filter(
                Q(id_sub_jenis_data__id_sub_jenis_data__icontains=nilai)
                | Q(id_ilap__nama_ilap__icontains=nilai)
            )
        if len(columns_search) > 3 and columns_search[3]:
            qs = qs.filter(durasi_prioritas__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:
            qs = qs.filter(durasi_non_prioritas__icontains=columns_search[4])

    records_filtered = qs.count()

    columns = [
        'seksi__name', 'tahun', 'id_ilap__nama_ilap',
        'durasi_prioritas', 'durasi_non_prioritas',
    ]
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'id'
            qs = qs.order_by(('-' if order_dir == 'desc' else '') + col)
        except Exception:
            qs = qs.order_by('seksi__name', '-tahun')
    else:
        qs = qs.order_by('seksi__name', '-tahun')

    data = []
    for obj in qs[start:start + length]:
        data.append({
            'seksi': SEKSI_LABELS.get(obj.seksi.name, obj.seksi.name),
            'tahun': obj.tahun,
            'cakupan': obj.cakupan,
            'durasi_prioritas': obj.durasi_prioritas,
            'durasi_non_prioritas': obj.durasi_non_prioritas,
            'actions': (
                f"<button class='btn btn-sm btn-primary me-1' data-action='edit' "
                f"data-url='{reverse('aturan_durasi_jatuh_tempo_update', args=[obj.pk])}' "
                f"title='Edit'><i class='feather-edit-2'></i></button>"
                f"<button class='btn btn-sm btn-danger' data-action='delete' "
                f"data-url='{reverse('aturan_durasi_jatuh_tempo_delete', args=[obj.pk])}' "
                f"title='Delete'><i class='feather-trash-2'></i></button>"
            ),
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
