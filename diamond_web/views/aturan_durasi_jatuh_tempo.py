"""Menu Aturan Durasi Jatuh Tempo — sumber angka Generate Otomatis.

Tabel ini yang menentukan berapa hari durasi jatuh tempo dipakai Generate
Otomatis dan Sinkronkan Prioritas pada menu Durasi Jatuh Tempo PIDE dan PMDE.
Sebelumnya angkanya konstanta di ``views/durasi_jatuh_tempo.py``, sehingga
mengubah durasi prioritas dari 45 ke 35 menuntut ubah kode dan deploy ulang.

Menunya terpisah per seksi — PIDE dan PMDE masing-masing punya halaman, URL,
dan hak akses sendiri, persis seperti menu Durasi Jatuh Tempo yang dilayaninya.
Admin satu seksi tidak melihat apalagi mengubah aturan seksi lain: setiap view
menyaring querysetnya ke seksinya sendiri, jadi menebak pk milik seksi lain
berujung 404, bukan halaman edit.

Kelas dasarnya dipakai bersama dan hanya dibedakan oleh ``seksi_name``; subkelas
PIDE dan PMDE di bawahnya tinggal menyebut seksi dan mixin haknya, supaya kedua
menu tidak bisa berbeda perilaku tanpa disengaja.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView
from urllib.parse import unquote_plus

from ..forms.aturan_durasi_jatuh_tempo import SEKSI_LABELS, AturanDurasiJatuhTempoForm
from ..models.aturan_durasi_jatuh_tempo import AturanDurasiJatuhTempo
from .mixins import (
    AdminPIDERequiredMixin,
    AdminPMDERequiredMixin,
    AjaxFormMixin,
    SafeDeleteMixin,
)

SEKSI_PIDE = 'user_pide'
SEKSI_PMDE = 'user_pmde'


class SeksiScopedMixin:
    """Mengunci sebuah view ke satu seksi.

    ``seksi_name`` diisi subkelas. Semua nama URL menu ini berpola
    ``aturan_durasi_jatuh_tempo_<pide|pmde>_<aksi>``, jadi cukup satu suffix
    untuk menyusunnya.
    """
    seksi_name = None

    @property
    def seksi_label(self):
        return SEKSI_LABELS[self.seksi_name]

    def url_name(self, suffix):
        return f'aturan_durasi_jatuh_tempo_{self.seksi_label.lower()}_{suffix}'

    def get_queryset(self):
        """Batasi ke aturan seksi ini — pk milik seksi lain jadi 404."""
        return AturanDurasiJatuhTempo.objects.filter(seksi__name=self.seksi_name)

    def get_seksi(self):
        return Group.objects.filter(name=self.seksi_name).first()


class AturanDurasiJatuhTempoListViewBase(
    LoginRequiredMixin, SeksiScopedMixin, TemplateView
):
    template_name = 'aturan_durasi_jatuh_tempo/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['seksi_label'] = self.seksi_label
        context['url_data'] = self.url_name('data')
        context['url_create'] = self.url_name('create')
        return context

    def get(self, request, *args, **kwargs):
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                messages.success(
                    request,
                    f'Aturan Durasi Jatuh Tempo "{unquote_plus(name)}" berhasil dihapus.',
                )
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


class AturanDurasiJatuhTempoCreateViewBase(
    LoginRequiredMixin, SeksiScopedMixin, AjaxFormMixin, CreateView
):
    model = AturanDurasiJatuhTempo
    form_class = AturanDurasiJatuhTempoForm
    template_name = 'aturan_durasi_jatuh_tempo/form.html'
    success_message = 'Aturan Durasi Jatuh Tempo "{object}" berhasil dibuat.'

    def get_success_url(self):
        return reverse(self.url_name('list'))

    def get_form_kwargs(self):
        """Seksi ditetapkan view, bukan dipilih pengguna — form tak punya fieldnya."""
        kwargs = super().get_form_kwargs()
        kwargs['seksi'] = self.get_seksi()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['seksi_label'] = self.seksi_label
        context['form_action'] = reverse(self.url_name('create'))
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


class AturanDurasiJatuhTempoUpdateViewBase(
    LoginRequiredMixin, SeksiScopedMixin, AjaxFormMixin, UpdateView
):
    model = AturanDurasiJatuhTempo
    form_class = AturanDurasiJatuhTempoForm
    template_name = 'aturan_durasi_jatuh_tempo/form.html'
    success_message = 'Aturan Durasi Jatuh Tempo "{object}" berhasil diperbarui.'

    def get_success_url(self):
        return reverse(self.url_name('list'))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['seksi'] = self.get_seksi()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['seksi_label'] = self.seksi_label
        context['form_action'] = reverse(self.url_name('update'), args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self.render_form_response(self.get_form())

    def form_valid(self, form):
        form.instance.update_date = timezone.now().date()
        form.instance.update_by = (getattr(self.request.user, 'username', '') or '')[:9]
        return super().form_valid(form)


class AturanDurasiJatuhTempoDeleteViewBase(
    SafeDeleteMixin, LoginRequiredMixin, SeksiScopedMixin, DeleteView
):
    """Hapus satu aturan.

    Menghapus aturan tidak mengubah baris ``DurasiJatuhTempo`` yang terlanjur
    dibuat darinya — angka yang sudah tertulis tetap berlaku sampai
    Sinkronkan Prioritas dijalankan lagi.
    """
    model = AturanDurasiJatuhTempo
    template_name = 'aturan_durasi_jatuh_tempo/confirm_delete.html'

    def get_success_url(self):
        return reverse(self.url_name('list'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['seksi_label'] = self.seksi_label
        context['form_action'] = reverse(self.url_name('delete'), args=[self.object.pk])
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


def _aturan_data(request, seksi_name):
    """Endpoint DataTables server-side, disaring ke satu seksi.

    Kolom Seksi tidak lagi ada di tabel — halamannya sudah milik satu seksi —
    sehingga indeks ``columns_search`` di sini bergeser satu dibanding versi
    gabungan sebelumnya.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = AturanDurasiJatuhTempo.objects.select_related(
        'seksi', 'id_ilap', 'id_sub_jenis_data'
    ).filter(seksi__name=seksi_name)
    records_total = qs.count()

    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:
            qs = qs.filter(tahun__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:
            nilai = columns_search[1]
            qs = qs.filter(
                Q(id_sub_jenis_data__id_sub_jenis_data__icontains=nilai)
                | Q(id_ilap__nama_ilap__icontains=nilai)
            )
        if len(columns_search) > 2 and columns_search[2]:
            qs = qs.filter(durasi_prioritas__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:
            qs = qs.filter(durasi_non_prioritas__icontains=columns_search[3])

    records_filtered = qs.count()

    columns = ['tahun', 'id_ilap__nama_ilap', 'durasi_prioritas', 'durasi_non_prioritas']
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'id'
            qs = qs.order_by(('-' if order_dir == 'desc' else '') + col)
        except Exception:
            qs = qs.order_by('-tahun')
    else:
        qs = qs.order_by('-tahun')

    label = SEKSI_LABELS[seksi_name].lower()
    data = []
    for obj in qs[start:start + length]:
        data.append({
            'tahun': obj.tahun,
            'cakupan': obj.cakupan,
            'durasi_prioritas': obj.durasi_prioritas,
            'durasi_non_prioritas': obj.durasi_non_prioritas,
            'actions': (
                f"<button class='btn btn-sm btn-primary me-1' data-action='edit' "
                f"data-url='{reverse(f'aturan_durasi_jatuh_tempo_{label}_update', args=[obj.pk])}' "
                f"title='Edit'><i class='feather-edit-2'></i></button>"
                f"<button class='btn btn-sm btn-danger' data-action='delete' "
                f"data-url='{reverse(f'aturan_durasi_jatuh_tempo_{label}_delete', args=[obj.pk])}' "
                f"title='Delete'><i class='feather-trash-2'></i></button>"
            ),
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


# ---------------------------------------------------------------------------
# PIDE
# ---------------------------------------------------------------------------

class AturanDurasiJatuhTempoPIDEListView(
    AdminPIDERequiredMixin, AturanDurasiJatuhTempoListViewBase
):
    seksi_name = SEKSI_PIDE


class AturanDurasiJatuhTempoPIDECreateView(
    AdminPIDERequiredMixin, AturanDurasiJatuhTempoCreateViewBase
):
    seksi_name = SEKSI_PIDE


class AturanDurasiJatuhTempoPIDEUpdateView(
    AdminPIDERequiredMixin, AturanDurasiJatuhTempoUpdateViewBase
):
    seksi_name = SEKSI_PIDE


class AturanDurasiJatuhTempoPIDEDeleteView(
    AdminPIDERequiredMixin, AturanDurasiJatuhTempoDeleteViewBase
):
    seksi_name = SEKSI_PIDE


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_GET
def aturan_durasi_jatuh_tempo_pide_data(request):
    return _aturan_data(request, SEKSI_PIDE)


# ---------------------------------------------------------------------------
# PMDE
# ---------------------------------------------------------------------------

class AturanDurasiJatuhTempoPMDEListView(
    AdminPMDERequiredMixin, AturanDurasiJatuhTempoListViewBase
):
    seksi_name = SEKSI_PMDE


class AturanDurasiJatuhTempoPMDECreateView(
    AdminPMDERequiredMixin, AturanDurasiJatuhTempoCreateViewBase
):
    seksi_name = SEKSI_PMDE


class AturanDurasiJatuhTempoPMDEUpdateView(
    AdminPMDERequiredMixin, AturanDurasiJatuhTempoUpdateViewBase
):
    seksi_name = SEKSI_PMDE


class AturanDurasiJatuhTempoPMDEDeleteView(
    AdminPMDERequiredMixin, AturanDurasiJatuhTempoDeleteViewBase
):
    seksi_name = SEKSI_PMDE


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def aturan_durasi_jatuh_tempo_pmde_data(request):
    return _aturan_data(request, SEKSI_PMDE)
