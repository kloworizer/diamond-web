from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.jenis_data_ilap import JenisDataILAP
from ..models.ilap import ILAP
import re
from ..forms.jenis_data_ilap import JenisDataILAPForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin

class JenisDataILAPListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    template_name = 'jenis_data_ilap/list.html'

    def get(self, request, *args, **kwargs):
        # If redirected after delete, show success message from query params
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Jenis Data "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class JenisDataILAPCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    model = JenisDataILAP
    form_class = JenisDataILAPForm
    template_name = 'jenis_data_ilap/form.html'
    success_url = reverse_lazy('jenis_data_ilap_list')
    success_message = 'Jenis Data "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('jenis_data_ilap_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

class JenisDataILAPUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    model = JenisDataILAP
    form_class = JenisDataILAPForm
    template_name = 'jenis_data_ilap/form.html'
    success_url = reverse_lazy('jenis_data_ilap_list')
    success_message = 'Jenis Data "{object}" berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('jenis_data_ilap_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

class JenisDataILAPDeleteView(LoginRequiredMixin, AdminP3DERequiredMixin, DeleteView):
    model = JenisDataILAP
    template_name = 'jenis_data_ilap/confirm_delete.html'
    success_url = reverse_lazy('jenis_data_ilap_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('jenis_data_ilap_delete', args=[self.object.pk])
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
        name = str(self.object)
        self.object.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Jenis Data "{name}" berhasil dihapus.'
            })
        messages.success(request, f'Jenis Data "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def jenis_data_ilap_data(request):
    """Server-side processing for DataTables.

    Accepts DataTables parameters: draw, start, length, search[value], order[0][column], order[0][dir]
    Returns JSON with draw, recordsTotal, recordsFiltered, data.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = JenisDataILAP.objects.select_related(
        'id_ilap',
        'id_ilap__id_kategori',
        'id_jenis_tabel'
    ).all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # ID Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Jenis Tabel
            qs = qs.filter(id_jenis_tabel__deskripsi__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Kategori ILAP
            qs = qs.filter(id_ilap__id_kategori__nama_kategori__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # ILAP
            qs = qs.filter(id_ilap__nama_ilap__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:  # Nama Jenis Data
            qs = qs.filter(nama_jenis_data__icontains=columns_search[4])
        if len(columns_search) > 5 and columns_search[5]:  # Nama Sub Jenis Data
            qs = qs.filter(nama_sub_jenis_data__icontains=columns_search[5])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_sub_jenis_data', 'id_jenis_tabel__deskripsi', 'id_ilap__id_kategori__nama_kategori', 
               'id_ilap__nama_ilap', 'nama_jenis_data', 'nama_sub_jenis_data']
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'id'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('id')
    else:
        qs = qs.order_by('id')

    qs_page = qs[start:start + length]

    data = []
    for obj in qs_page:
        data.append({
            'id_sub_jenis_data': obj.id_sub_jenis_data,
            'jenis_tabel': str(obj.id_jenis_tabel),
            'kategori_ilap': str(obj.id_ilap.id_kategori),
            'ilap': str(obj.id_ilap),
            'nama_jenis_data': obj.nama_jenis_data,
            'nama_sub_jenis_data': obj.nama_sub_jenis_data,
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('jenis_data_ilap_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('jenis_data_ilap_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })



@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def get_next_jenis_data_id(request):
    """Get next id_jenis_data for a given ILAP prefix.

    Expects `ilap_id` GET parameter which is the ILAP prefix (e.g. 'AS001').
    Returns JSON: {'next_id': 'AS00102'}
    """
    ilap_id = request.GET.get('ilap_id')
    if not ilap_id:
        return JsonResponse({'error': 'ilap_id is required'}, status=400)

    # Normalize the prefix: if a numeric PK is passed, resolve to the ILAP.code (id_ilap).
    prefix = ilap_id
    try:
        # numeric PK case
        pk = int(ilap_id)
        ilap_obj = ILAP.objects.filter(pk=pk).first()
        if ilap_obj:
            prefix = ilap_obj.id_ilap
    except Exception:
        # not an integer; try to extract an alphanumeric prefix from the string
        m = re.match(r"([A-Za-z0-9]+)", ilap_id.strip())
        if m:
            prefix = m.group(1)

    # Get the last id_jenis_data for this ILAP prefix
    last = JenisDataILAP.objects.filter(id_jenis_data__startswith=prefix).order_by('-id_jenis_data').first()

    if last:
        suffix = last.id_jenis_data[len(prefix):]
        try:
            last_number = int(suffix)
        except Exception:
            last_number = 0
        next_number = last_number + 1
    else:
        next_number = 1

    # Format with 2 digits as requested (AS00101 -> AS00102)
    next_id = f"{prefix}{next_number:02d}"

    return JsonResponse({'next_id': next_id})



@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def get_existing_jenis_data(request):
    """Return list of existing id_jenis_data for a given ILAP prefix or PK.

    Returns JSON: {'items': [{'value': 'AS00101', 'text': 'AS00101 - Nama'}, ...]}
    """
    ilap_id = request.GET.get('ilap_id')
    if not ilap_id:
        return JsonResponse({'items': []})

    # normalize as in get_next_jenis_data_id
    prefix = ilap_id
    try:
        pk = int(ilap_id)
        ilap_obj = ILAP.objects.filter(pk=pk).first()
        if ilap_obj:
            prefix = ilap_obj.id_ilap
    except Exception:
        m = re.match(r"([A-Za-z0-9]+)", ilap_id.strip())
        if m:
            prefix = m.group(1)

    # use values + distinct to return unique id_jenis_data entries
    qs = JenisDataILAP.objects.filter(id_jenis_data__startswith=prefix).values('id_jenis_data', 'nama_jenis_data').distinct().order_by('id_jenis_data')
    items = []
    for j in qs:
        items.append({'value': j['id_jenis_data'], 'text': f"{j['id_jenis_data']} - {j['nama_jenis_data']}"})

    return JsonResponse({'items': items})



@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def get_existing_sub_jenis_data(request):
    """Return existing id_sub_jenis_data for a given id_jenis_data.

    Returns JSON: {'items': [{'value': 'KM0330101', 'text': 'KM0330101 - Nama Sub'}, ...]}
    """
    id_jenis = request.GET.get('id_jenis_data')
    if not id_jenis:
        return JsonResponse({'items': []})

    qs = JenisDataILAP.objects.filter(id_jenis_data__startswith=id_jenis).values('id_sub_jenis_data', 'nama_sub_jenis_data').distinct().order_by('id_sub_jenis_data')
    items = []
    for j in qs:
        items.append({'value': j['id_sub_jenis_data'], 'text': f"{j['id_sub_jenis_data']} - {j['nama_sub_jenis_data']}"})
    return JsonResponse({'items': items})



@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def get_next_sub_jenis_id(request):
    """Get next id_sub_jenis_data for a given id_jenis_data prefix.

    Expects `id_jenis_data` GET parameter. Returns JSON: {'next_id': '<id_jenis_data>01'}
    """
    id_jenis = request.GET.get('id_jenis_data')
    if not id_jenis:
        return JsonResponse({'error': 'id_jenis_data is required'}, status=400)

    last = JenisDataILAP.objects.filter(id_sub_jenis_data__startswith=id_jenis).order_by('-id_sub_jenis_data').first()
    if last:
        suffix = last.id_sub_jenis_data[len(id_jenis):]
        try:
            last_number = int(suffix)
        except Exception:
            last_number = 0
        next_number = last_number + 1
    else:
        next_number = 1

    next_id = f"{id_jenis}{next_number:02d}"
    return JsonResponse({'next_id': next_id})
