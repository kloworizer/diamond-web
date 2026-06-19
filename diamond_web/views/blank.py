from django.shortcuts import render

def blank_index(request):
    """Render a blank/empty page.

    Serves as a placeholder page with minimal content. Can be used as a
    starting point for building new features or as a fallback page.

    Args:
        request (HttpRequest): The incoming HTTP request object.

    Returns:
        HttpResponse: Rendered blank template with page title context.
    """
    context = {
        'title': 'Halaman Kosong',
    }
    return render(request, 'fe_blank/blank.html', context)


