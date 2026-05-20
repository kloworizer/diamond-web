from django.shortcuts import render

def data_prioritas_idx(request):
    # Logika data Anda di sini
    context = {
        'title': 'Data Prioritas',
    }
    return render(request, 'fe_data_prioritas/fe_data_prioritas.html', context)


