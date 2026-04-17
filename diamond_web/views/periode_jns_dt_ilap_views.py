from django.shortcuts import render

def periode_jns_data_ilap_idx(request):
    # Logika data Anda di sini
    context = {
        'title': 'Periode Jenis Data ILAP',
    }
    return render(request, 'fe_periode_jns_dt_ilap/periode_jns_dt_ilap.html', context)