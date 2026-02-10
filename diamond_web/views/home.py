from django.shortcuts import render
from django.conf import settings
from django.contrib.auth.models import Group
from diamond_web.views.task_to_do import (
    get_tiket_summary_for_user,
    get_tiket_summary_for_user_pide,
    get_tiket_summary_for_user_pmde,
)

def home(request):
    """Render the application home page.

    Context provided to template:
    - `is_p3de` (bool): whether the current authenticated user belongs to
      `user_p3de` group. Used to show P3DE-specific UI.
    - `tiket_summary` (dict): when `is_p3de` is True, contains counts of
      actionable tiket items for the logged-in P3DE (uses
      `get_tiket_summary_for_user`). Example keys: `rekam_backup_data`,
      `buat_tanda_terima`, `rekam_hasil_penelitian`, `kirim_ke_pide`.
    - `debug_user_groups` (dict): only present when `settings.DEBUG` is
      True; includes three admin groups and their member lists for UI
      debugging.

    Usage: GET request; returns rendered `home.html` with the above context.
    """
    context = {}
    # expose user role membership for templates
    is_p3de = False
    is_pide = False
    is_pmde = False
    if request.user.is_authenticated:
        is_p3de = request.user.groups.filter(name='user_p3de').exists()
        is_pide = request.user.groups.filter(name='user_pide').exists()
        is_pmde = request.user.groups.filter(name='user_pmde').exists()
    context['is_p3de'] = is_p3de
    context['is_pide'] = is_pide
    context['is_pmde'] = is_pmde
    # compute task summary based on user role
    if is_p3de:
        context['tiket_summary'] = get_tiket_summary_for_user(request.user)
    if is_pide:
        context['tiket_summary_pide'] = get_tiket_summary_for_user_pide(request.user)
    if is_pmde:
        context['tiket_summary_pmde'] = get_tiket_summary_for_user_pmde(request.user)
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