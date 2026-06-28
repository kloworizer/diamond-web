from django.shortcuts import render

def periode_jns_data_ilap_idx(request):
    """Render the Periode Jenis Data ILAP index page.

    Displays the frontend page for managing ILAP data period types.
    Provides a title context for the template to use.

    Args:
        request (HttpRequest): The incoming HTTP request object.

    Returns:
        HttpResponse: Rendered periode jenis data ILAP template.
    """
    context = {
        'title': 'Periode Jenis Data ILAP',
    }
    return render(request, 'fe_periode_jns_dt_ilap/periode_jns_dt_ilap.html', context)