from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_protect

from ..models.jenis_data_ilap import JenisDataILAP
from ..models.ilap import ILAP

def _is_pide_user(user):
    """Check if user is PIDE user or admin."""
    return user.is_superuser or user.is_staff or user.groups.filter(name__in=['user_pide', 'admin', 'admin_pide']).exists()

@login_required
@user_passes_test(_is_pide_user)
@require_GET
@csrf_protect
def laporan_pide_filter_options(request):
    """AJAX endpoint to return filtered options for cascading dropdowns."""
    id_ilap = request.GET.get('id_ilap')
    id_jenis_data = request.GET.get('id_jenis_data')
    nama_sub_jenis_data = request.GET.get('nama_sub_jenis_data')
    nama_tabel_I = request.GET.get('nama_tabel_I')
    
    # Base queryset for subjenis datailap
    qs = JenisDataILAP.objects.all()
    
    # Apply filters to narrow down the available choices
    if id_ilap and id_ilap != 'all' and id_ilap != '':
        qs = qs.filter(id_ilap_id=id_ilap)
    if id_jenis_data and id_jenis_data != 'all' and id_jenis_data != '':
        qs = qs.filter(id=id_jenis_data)
    if nama_sub_jenis_data and nama_sub_jenis_data != 'all' and nama_sub_jenis_data != '':
        qs = qs.filter(nama_sub_jenis_data=nama_sub_jenis_data)
    if nama_tabel_I and nama_tabel_I != 'all' and nama_tabel_I != '':
        qs = qs.filter(nama_tabel_I=nama_tabel_I)
        
    # Get distinct values for each field based on the narrowed queryset
    # 1. ILAPs: If no ILAP selected, show all available ones
    ilap_ids = qs.values_list('id_ilap_id', flat=True).distinct()
    ilaps = ILAP.objects.filter(id__in=ilap_ids).values('id', 'nama_ilap').order_by('nama_ilap')
    
    # 2. Jenis Data (Subjenis level in our form)
    jenis_data = qs.values('id', 'nama_sub_jenis_data', 'id_sub_jenis_data').order_by('nama_sub_jenis_data').distinct()
    
    # 3. nama_sub_jenis_data (CharField group)
    sub_jenis_choices = qs.values_list('nama_sub_jenis_data', flat=True).order_by('nama_sub_jenis_data').distinct()
    
    # 4. nama_tabel_I (CharField group)
    tabel_i_choices = qs.values_list('nama_tabel_I', flat=True).order_by('nama_tabel_I').distinct()
    
    return JsonResponse({
        'ilaps': list(ilaps),
        'jenis_data': list(jenis_data),
        'sub_jenis': list(sub_jenis_choices),
        'tabel_i': list(tabel_i_choices)
    })
