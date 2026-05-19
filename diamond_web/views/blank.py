from django.shortcuts import render

def blank_index(request):
    # Logika data Anda di sini
    context = {
        'title': 'Halaman Kosong',
    }
    return render(request, 'fe_blank/blank.html', context)


