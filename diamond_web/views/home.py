from django.shortcuts import render
from django.conf import settings
from django.contrib.auth.models import Group
from diamond_web.views.task_to_do import get_tiket_summary_for_user

def home(request):
    context = {}
    # expose whether the current user is in user_p3de group for templates
    is_p3de = False
    if request.user.is_authenticated:
        is_p3de = request.user.groups.filter(name='user_p3de').exists()
    context['is_p3de'] = is_p3de
    # if p3de, compute task summary for inline display on home using helper
    if is_p3de:
        context['tiket_summary'] = get_tiket_summary_for_user(request.user)
    if settings.DEBUG:
        groups = Group.objects.filter(name__in=['user_p3de', 'user_pide', 'user_pmde']).prefetch_related('user_set')
        debug_groups = {}
        for group in groups:
            users = group.user_set.all().order_by('username')
            debug_groups[group.name] = [
                {
                    'username': user.username,
                    'full_name': user.get_full_name() or '-'
                }
                for user in users
            ]
        context['debug_user_groups'] = debug_groups
    return render(request, 'home.html', context)