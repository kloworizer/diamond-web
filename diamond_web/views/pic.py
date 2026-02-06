from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.pic import PIC
from ..forms.pic import PICForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin, AdminPIDERequiredMixin, AdminPMDERequiredMixin


class PICListView(LoginRequiredMixin, TemplateView):
    """Base list view for all PIC types"""
    template_name = 'pic/list.html'
    tipe = None
    
    def get_tipe_display(self):
        """Get display name for the tipe"""
        if self.tipe:
            return dict(PIC.TipePIC.choices).get(self.tipe, self.tipe)
        return "PIC"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipe'] = self.tipe
        context['tipe_display'] = self.get_tipe_display()
        return context

    def get(self, request, *args, **kwargs):
        # If redirected after delete, show success message from query params
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'{self.get_tipe_display()} "{name}" deleted successfully.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


class PICCreateView(LoginRequiredMixin, AjaxFormMixin, CreateView):
    """Base create view for all PIC types"""
    model = PIC
    form_class = PICForm
    template_name = 'pic/form.html'
    tipe = None
    
    def get_tipe_display(self):
        """Get display name for the tipe"""
        if self.tipe:
            return dict(PIC.TipePIC.choices).get(self.tipe, self.tipe)
        return "PIC"
    
    def get_success_url(self):
        tipe_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_list',
            PIC.TipePIC.PIDE: 'pic_pide_list',
            PIC.TipePIC.PMDE: 'pic_pmde_list',
        }
        return reverse_lazy(tipe_url_map.get(self.tipe, 'home'))
    
    @property
    def success_message(self):
        return f'{self.get_tipe_display()} "{{object}}" created successfully.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tipe'] = self.tipe
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipe'] = self.tipe
        context['tipe_display'] = self.get_tipe_display()
        tipe_create_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_create',
            PIC.TipePIC.PIDE: 'pic_pide_create',
            PIC.TipePIC.PMDE: 'pic_pmde_create',
        }
        context['form_action'] = reverse(tipe_create_url_map.get(self.tipe, 'home'))
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)


class PICUpdateView(LoginRequiredMixin, AjaxFormMixin, UpdateView):
    """Base update view for all PIC types"""
    model = PIC
    form_class = PICForm
    template_name = 'pic/form.html'
    tipe = None
    
    def get_tipe_display(self):
        """Get display name for the tipe"""
        if self.tipe:
            return dict(PIC.TipePIC.choices).get(self.tipe, self.tipe)
        return "PIC"
    
    def get_success_url(self):
        tipe_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_list',
            PIC.TipePIC.PIDE: 'pic_pide_list',
            PIC.TipePIC.PMDE: 'pic_pmde_list',
        }
        return reverse_lazy(tipe_url_map.get(self.tipe, 'home'))
    
    @property
    def success_message(self):
        return f'{self.get_tipe_display()} "{{object}}" updated successfully.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tipe'] = self.tipe
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipe'] = self.tipe
        context['tipe_display'] = self.get_tipe_display()
        tipe_update_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_update',
            PIC.TipePIC.PIDE: 'pic_pide_update',
            PIC.TipePIC.PMDE: 'pic_pmde_update',
        }
        context['form_action'] = reverse(tipe_update_url_map.get(self.tipe, 'home'), args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)
    
    def get_queryset(self):
        """Filter by tipe to ensure users only access their PIC type"""
        qs = super().get_queryset()
        if self.tipe:
            qs = qs.filter(tipe=self.tipe)
        return qs


class PICDeleteView(LoginRequiredMixin, DeleteView):
    """Base delete view for all PIC types"""
    model = PIC
    template_name = 'pic/confirm_delete.html'
    tipe = None
    
    def get_tipe_display(self):
        """Get display name for the tipe"""
        if self.tipe:
            return dict(PIC.TipePIC.choices).get(self.tipe, self.tipe)
        return "PIC"
    
    def get_success_url(self):
        tipe_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_list',
            PIC.TipePIC.PIDE: 'pic_pide_list',
            PIC.TipePIC.PMDE: 'pic_pmde_list',
        }
        return reverse_lazy(tipe_url_map.get(self.tipe, 'home'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipe'] = self.tipe
        context['tipe_display'] = self.get_tipe_display()
        tipe_delete_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_delete',
            PIC.TipePIC.PIDE: 'pic_pide_delete',
            PIC.TipePIC.PMDE: 'pic_pmde_delete',
        }
        context['form_action'] = reverse(tipe_delete_url_map.get(self.tipe, 'home'), args=[self.object.pk])
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
                'message': f'{self.get_tipe_display()} "{name}" deleted successfully.'
            })
        messages.success(request, f'{self.get_tipe_display()} "{name}" deleted successfully.')
        return JsonResponse({'success': True, 'redirect': self.get_success_url()})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
    
    def get_queryset(self):
        """Filter by tipe to ensure users only access their PIC type"""
        qs = super().get_queryset()
        if self.tipe:
            qs = qs.filter(tipe=self.tipe)
        return qs


# Concrete views for each PIC type
class PICP3DEListView(AdminP3DERequiredMixin, PICListView):
    tipe = PIC.TipePIC.P3DE
    template_name = 'pic_p3de/list.html'  # Keep old template for backward compatibility


class PICP3DECreateView(AdminP3DERequiredMixin, PICCreateView):
    tipe = PIC.TipePIC.P3DE
    template_name = 'pic_p3de/form.html'


class PICP3DEUpdateView(AdminP3DERequiredMixin, PICUpdateView):
    tipe = PIC.TipePIC.P3DE
    template_name = 'pic_p3de/form.html'


class PICP3DEDeleteView(AdminP3DERequiredMixin, PICDeleteView):
    tipe = PIC.TipePIC.P3DE
    template_name = 'pic_p3de/confirm_delete.html'


class PICPIDEListView(AdminPIDERequiredMixin, PICListView):
    tipe = PIC.TipePIC.PIDE
    template_name = 'pic_pide/list.html'


class PICPIDECreateView(AdminPIDERequiredMixin, PICCreateView):
    tipe = PIC.TipePIC.PIDE
    template_name = 'pic_pide/form.html'


class PICPIDEUpdateView(AdminPIDERequiredMixin, PICUpdateView):
    tipe = PIC.TipePIC.PIDE
    template_name = 'pic_pide/form.html'


class PICPIDEDeleteView(AdminPIDERequiredMixin, PICDeleteView):
    tipe = PIC.TipePIC.PIDE
    template_name = 'pic_pide/confirm_delete.html'


class PICPMDEListView(AdminPMDERequiredMixin, PICListView):
    tipe = PIC.TipePIC.PMDE
    template_name = 'pic_pmde/list.html'


class PICPMDECreateView(AdminPMDERequiredMixin, PICCreateView):
    tipe = PIC.TipePIC.PMDE
    template_name = 'pic_pmde/form.html'


class PICPMDEUpdateView(AdminPMDERequiredMixin, PICUpdateView):
    tipe = PIC.TipePIC.PMDE
    template_name = 'pic_pmde/form.html'


class PICPMDEDeleteView(AdminPMDERequiredMixin, PICDeleteView):
    tipe = PIC.TipePIC.PMDE
    template_name = 'pic_pmde/confirm_delete.html'


# DataTables server-side processing
def _pic_data_common(request, tipe):
    """Common function for DataTables server-side processing"""
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = PIC.objects.filter(tipe=tipe).select_related('id_sub_jenis_data_ilap', 'id_user').all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # Sub Jenis Data ILAP
            qs = qs.filter(id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # User
            from django.db.models import Q
            qs = qs.filter(Q(id_user__username__icontains=columns_search[1]) | 
                          Q(id_user__first_name__icontains=columns_search[1]) |
                          Q(id_user__last_name__icontains=columns_search[1]))
        if len(columns_search) > 2 and columns_search[2]:  # Start Date
            qs = qs.filter(start_date__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # End Date
            qs = qs.filter(end_date__icontains=columns_search[3])

    # Global search
    search_value = request.GET.get('search[value]')
    if search_value:
        from django.db.models import Q
        qs = qs.filter(
            Q(id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=search_value) |
            Q(id_user__username__icontains=search_value) |
            Q(id_user__first_name__icontains=search_value) |
            Q(id_user__last_name__icontains=search_value) |
            Q(start_date__icontains=search_value) |
            Q(end_date__icontains=search_value)
        )

    records_filtered = qs.count()

    # Ordering
    order_column_idx = int(request.GET.get('order[0][column]', '0'))
    order_dir = request.GET.get('order[0][dir]', 'asc')
    order_columns = ['id_sub_jenis_data_ilap__nama_sub_jenis_data', 'id_user__username', 'start_date', 'end_date']
    if 0 <= order_column_idx < len(order_columns):
        order_field = order_columns[order_column_idx]
        if order_dir == 'desc':
            order_field = f'-{order_field}'
        qs = qs.order_by(order_field)

    # Pagination
    qs = qs[start:start + length]

    # Map tipe to URL names
    tipe_url_map = {
        PIC.TipePIC.P3DE: ('pic_p3de_update', 'pic_p3de_delete'),
        PIC.TipePIC.PIDE: ('pic_pide_update', 'pic_pide_delete'),
        PIC.TipePIC.PMDE: ('pic_pmde_update', 'pic_pmde_delete'),
    }
    update_url_name, delete_url_name = tipe_url_map.get(tipe, ('', ''))

    # Format data
    data = []
    for obj in qs:
        user_display = f"{obj.id_user.first_name} {obj.id_user.last_name}".strip()
        if not user_display:
            user_display = obj.id_user.username
        
        data.append({
            'id': obj.id,
            'sub_jenis_data_ilap': obj.id_sub_jenis_data_ilap.nama_sub_jenis_data,
            'user': user_display,
            'start_date': obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '',
            'end_date': obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse(update_url_name, args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse(delete_url_name, args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
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
def pic_p3de_data(request):
    """Server-side processing for P3DE DataTables"""
    return _pic_data_common(request, PIC.TipePIC.P3DE)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_GET
def pic_pide_data(request):
    """Server-side processing for PIDE DataTables"""
    return _pic_data_common(request, PIC.TipePIC.PIDE)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def pic_pmde_data(request):
    """Server-side processing for PMDE DataTables"""
    return _pic_data_common(request, PIC.TipePIC.PMDE)
