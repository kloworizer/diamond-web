"""Views for DOCX Template management."""

from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET, require_http_methods
from django.shortcuts import render

from ..models.docx_template import DocxTemplate
from ..forms.docx_template import DocxTemplateForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin, SafeDeleteMixin


class DocxTemplateListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    """List view for `DocxTemplate` entries."""
    template_name = 'docx_template/list.html'

    def get(self, request, *args, **kwargs):
        """Render the list template and surface optional delete message."""
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Template dokumen "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['templates'] = DocxTemplate.objects.all().order_by('-updated_at')
        return context


class DocxTemplateCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `DocxTemplate`."""
    model = DocxTemplate
    form_class = DocxTemplateForm
    template_name = 'docx_template/form.html'
    success_url = reverse_lazy('docx_template_list')
    success_message = 'Template dokumen "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = 'create'
        context['form_url'] = reverse_lazy('docx_template_create')
        return context

    def get(self, request, *args, **kwargs):
        """Return the create form rendered for AJAX or full-page requests."""
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)


class DocxTemplateUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for `DocxTemplate`."""
    model = DocxTemplate
    form_class = DocxTemplateForm
    template_name = 'docx_template/form.html'
    success_url = reverse_lazy('docx_template_list')
    success_message = 'Template dokumen "{object}" berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = 'update'
        context['form_url'] = reverse_lazy('docx_template_update', kwargs={'pk': self.object.pk})
        return context


class DocxTemplateDeleteView(LoginRequiredMixin, AdminP3DERequiredMixin, SafeDeleteMixin, DeleteView):
    """Delete view for `DocxTemplate`."""
    model = DocxTemplate
    success_url = reverse_lazy('docx_template_list')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        return obj

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        obj_name = str(obj)
        response = super().delete(request, *args, **kwargs)
        if response.status_code == 302:  # Successful redirect
            from django.shortcuts import redirect
            return redirect(f'{self.success_url}?deleted=true&name={quote_plus(obj_name)}')
        return response


@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='admin').exists() or u.groups.filter(name='admin_p3de').exists())
@require_GET
def docx_template_data(request):
    """Return template data as JSON for DataTable."""
    # Get all templates
    queryset = DocxTemplate.objects.all().order_by('-updated_at')
    
    # Handle DataTable server-side parameters
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    
    # Filter by columns if provided
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search and len(columns_search) > 0:
        if columns_search[0]:  # nama_template search
            queryset = queryset.filter(nama_template__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # jenis_dokumen search
            queryset = queryset.filter(jenis_dokumen__icontains=columns_search[1])
    
    # Get total count before pagination
    total_records = queryset.count()
    
    # Apply pagination
    records = queryset[start:start + length]
    
    # Build response data
    data = []
    for template in records:
        edit_url = reverse_lazy('docx_template_update', kwargs={'pk': template.id})
        delete_url = reverse_lazy('docx_template_delete', kwargs={'pk': template.id})
        actions = f'''
            <button class="btn btn-sm btn-primary" data-action="edit" data-url="{edit_url}">
                <i class="ri-edit-line"></i>
            </button>
            <button class="btn btn-sm btn-danger" data-action="delete" data-url="{delete_url}">
                <i class="ri-delete-line"></i>
            </button>
        '''
        data.append({
            'nama_template': template.nama_template,
            'jenis_dokumen': dict(DocxTemplate.DOCUMENT_TYPE_CHOICES).get(template.jenis_dokumen, template.jenis_dokumen),
            'active': '<span class="badge bg-success">Ya</span>' if template.active else '<span class="badge bg-danger">Tidak</span>',
            'updated_at': template.updated_at.strftime('%d/%m/%Y %H:%M'),
            'actions': actions,
        })
    
    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })
