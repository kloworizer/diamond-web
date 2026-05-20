from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

@login_required
def index(request):
    """Render the dashboard home page.

    Displays the main dashboard interface for authenticated users.
    Template: dashboard/index.html

    Args:
        request (HttpRequest): The HTTP request object from an authenticated user.

    Returns:
        HttpResponse: Rendered dashboard template.
    """
    return render(request, 'dashboard/index.html')


class DashboardMonitoringView(LoginRequiredMixin, TemplateView):
    """Dashboard view that embeds Power BI monitoring report."""
    template_name = 'dashboard/monitoring.html'
    login_url = 'login'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['powerbi_url'] = 'https://pbidemo.intranet.pajak.go.id/pbidevelopmentportal/powerbi/PDE/DDE-Mon%20Tiket%20New?rs:embed=true'
        return context