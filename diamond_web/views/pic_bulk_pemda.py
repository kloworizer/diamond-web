"""Bulk PIC assignment for Pemda (PD) and Provinsi (PV) jenis data.

A Pemda/Provinsi sub jenis data code is ``<prefix><pemda:3><kode:4>`` - e.g.
``PD0014101`` is pemda ``001`` reporting jenis data ``4101`` (TDP). The same
``4101`` exists once for every pemda and provinsi, so handing it to a new PIC
one row at a time means hundreds of edits. This page applies one PIC change to
every ``P?xxx<kode>`` row at once.

Every change goes through the same helpers as the single-row PIC views
(`_assign_pic_to_open_tikets`, `_propagate_pic_update`,
`_delete_pic_with_tikets`), so tikets and their `TiketAction` trail end up
exactly as if each row had been edited by hand.

The flow is preview -> confirm: `pic_bulk_pemda_preview` returns what would
happen per row without writing anything, and `pic_bulk_pemda_execute` rebuilds
that plan for the rows the admin kept ticked and applies it in one transaction.
"""
from collections import defaultdict
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView

from ..models.pic import PIC
from ..utils.pemda_kode import (
    KODE_RE as _KODE_RE,
    SCOPE_PREFIXES,
    jenis_data_for_kode as _jenis_data_for,
    kode_options as _kode_options,
)
from .pic import (
    _assign_pic_to_open_tikets,
    _delete_pic_with_tikets,
    _propagate_pic_update,
    _tiket_role_for,
)

MODE_TAMBAH = 'tambah'
MODE_GANTI = 'ganti'
MODE_AKHIRI = 'akhiri'
MODE_HAPUS = 'hapus'
MODES = (MODE_TAMBAH, MODE_GANTI, MODE_AKHIRI, MODE_HAPUS)

_ADMIN_GROUP = {
    PIC.TipePIC.P3DE: 'admin_p3de',
    PIC.TipePIC.PIDE: 'admin_pide',
    PIC.TipePIC.PMDE: 'admin_pmde',
}
# The pool a new PIC may be picked from - the same one `PICForm` offers.
_USER_GROUP = {
    PIC.TipePIC.P3DE: 'user_p3de',
    PIC.TipePIC.PIDE: 'user_pide',
    PIC.TipePIC.PMDE: 'user_pmde',
}


class BulkPemdaError(Exception):
    """A request the admin has to correct; its message is shown as-is."""


def _allowed_tipes(user):
    """PIC types `user` may administer, in `PIC.TipePIC` order."""
    if not user.is_authenticated:
        return []
    groups = set(user.groups.values_list('name', flat=True))
    if user.is_superuser or 'admin' in groups:
        return list(PIC.TipePIC.values)
    return [tipe for tipe in PIC.TipePIC.values if _ADMIN_GROUP[tipe] in groups]


def _nama_user(user):
    full_name = f'{user.first_name} {user.last_name}'.strip()
    return f'{full_name} ({user.username})' if full_name else user.username


def _pick_user(raw, tipe, label):
    """Resolve a user id from the request, limited to the tipe's user group."""
    try:
        pk = int(raw)
    except (TypeError, ValueError):
        raise BulkPemdaError(f'{label} wajib dipilih.')
    user = User.objects.filter(pk=pk, groups__name=_USER_GROUP[tipe]).first()
    if user is None:
        raise BulkPemdaError(f'{label} tidak ditemukan di grup {_USER_GROUP[tipe]}.')
    return user


def _parse_date(raw, label):
    if not raw:
        raise BulkPemdaError(f'{label} wajib diisi.')
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise BulkPemdaError(f'{label} tidak valid.')


def _parse_params(request, data):
    """Validate the bulk form; raise `BulkPemdaError` for anything wrong."""
    tipe = data.get('tipe')
    if tipe not in _allowed_tipes(request.user):
        raise BulkPemdaError('Anda tidak berwenang mengubah PIC untuk tipe ini.')

    kode = (data.get('kode') or '').strip()
    if not _KODE_RE.match(kode):
        raise BulkPemdaError('Kode jenis data harus 4 digit, misalnya 4101.')

    scope = data.get('scope') or 'ALL'
    if scope not in SCOPE_PREFIXES:
        raise BulkPemdaError('Cakupan tidak valid.')

    mode = data.get('mode')
    if mode not in MODES:
        raise BulkPemdaError('Aksi tidak valid.')

    params = {
        'tipe': tipe, 'kode': kode, 'scope': scope, 'mode': mode,
        'user_lama': None, 'user_baru': None,
        'start_date': None, 'end_date': None, 'hanya_aktif': True,
    }

    if mode != MODE_TAMBAH and data.get('user_lama'):
        try:
            params['user_lama'] = User.objects.get(pk=int(data['user_lama']))
        except (User.DoesNotExist, ValueError):
            raise BulkPemdaError('PIC lama tidak ditemukan.')

    if mode == MODE_TAMBAH:
        params['user_baru'] = _pick_user(data.get('user_baru'), tipe, 'PIC baru')
        params['start_date'] = _parse_date(data.get('start_date'), 'Tanggal Mulai')
    elif mode == MODE_GANTI:
        params['user_baru'] = _pick_user(data.get('user_baru'), tipe, 'PIC baru')
        if params['user_lama'] and params['user_lama'].pk == params['user_baru'].pk:
            raise BulkPemdaError('PIC lama dan PIC baru tidak boleh sama.')
    elif mode == MODE_AKHIRI:
        params['end_date'] = _parse_date(data.get('end_date'), 'Tanggal Berakhir')
    elif mode == MODE_HAPUS:
        params['hanya_aktif'] = str(data.get('hanya_aktif', '1')).lower() in ('1', 'true', 'on')

    return params


def _row(key, jd, pics_by_jd, ok, keterangan, pic=None):
    aktif = [p for p in pics_by_jd.get(jd.pk, []) if p.end_date is None]
    return {
        'key': key,
        'id_sub_jenis_data': jd.id_sub_jenis_data,
        'nama_ilap': jd.id_ilap.nama_ilap,
        'nama_sub_jenis_data': jd.nama_sub_jenis_data,
        'pic_aktif': [_nama_user(p.id_user) for p in aktif],
        'pic_target': _nama_user(pic.id_user) if pic else '',
        'ok': ok,
        'keterangan': keterangan,
        # Kept server-side only; stripped before the preview is serialised.
        '_jd': jd,
        '_pic': pic,
    }


def _build_plan(params, selected=None):
    """Work out, row by row, what the bulk request would do.

    `selected` narrows the plan to the given row keys *before* it is worked out,
    so each row is judged against what the rows actually being applied leave
    behind - e.g. when two old PICs of one jenis data are both handed to the
    same user, the second becomes a close rather than a duplicate active PIC.
    """
    tipe, mode = params['tipe'], params['mode']
    jenis_data = list(_jenis_data_for(params['kode'], params['scope']))
    jd_by_pk = {jd.pk: jd for jd in jenis_data}

    pics_by_jd = defaultdict(list)
    for pic in (
        PIC.objects.filter(tipe=tipe, id_sub_jenis_data_ilap__in=list(jd_by_pk))
        .select_related('id_user')
        .order_by('start_date', 'id')
    ):
        pics_by_jd[pic.id_sub_jenis_data_ilap_id].append(pic)

    # Users that will hold an open PIC per jenis data, updated as rows are
    # planned so later rows see the effect of earlier ones.
    aktif = {
        pk: {p.id_user_id for p in pics if p.end_date is None}
        for pk, pics in pics_by_jd.items()
    }

    def taken(pk, user, start):
        return any(p.id_user_id == user.pk and p.start_date == start for p in pics_by_jd.get(pk, []))

    rows = []

    if mode == MODE_TAMBAH:
        user, start = params['user_baru'], params['start_date']
        for jd in jenis_data:
            key = f'jd-{jd.pk}'
            if selected is not None and key not in selected:
                continue
            holders = aktif.setdefault(jd.pk, set())
            if user.pk in holders:
                rows.append(_row(key, jd, pics_by_jd, False, 'Sudah menjadi PIC aktif.'))
            elif taken(jd.pk, user, start):
                rows.append(_row(key, jd, pics_by_jd, False,
                                 f'Sudah ada PIC {user.username} dengan Tanggal Mulai {start}.'))
            else:
                holders.add(user.pk)
                rows.append(_row(key, jd, pics_by_jd, True, f'Tambah {_nama_user(user)}.'))
        return rows

    # The other modes act on existing PIC rows.
    targets = []
    for jd in jenis_data:
        for pic in pics_by_jd.get(jd.pk, []):
            if params['user_lama'] and pic.id_user_id != params['user_lama'].pk:
                continue
            if (mode != MODE_HAPUS or params['hanya_aktif']) and pic.end_date is not None:
                continue
            key = f'pic-{pic.pk}'
            if selected is not None and key not in selected:
                continue
            targets.append((key, jd, pic))

    today = timezone.now().date()
    for key, jd, pic in targets:
        holders = aktif.setdefault(jd.pk, set())

        if mode == MODE_HAPUS:
            holders.discard(pic.id_user_id)
            rows.append(_row(key, jd, pics_by_jd, True, 'Hapus PIC.', pic))

        elif mode == MODE_AKHIRI:
            end = params['end_date']
            if end < pic.start_date:
                rows.append(_row(key, jd, pics_by_jd, False,
                                 f'Tanggal Berakhir sebelum Tanggal Mulai ({pic.start_date}).', pic))
            else:
                holders.discard(pic.id_user_id)
                rows.append(_row(key, jd, pics_by_jd, True, f'Akhiri per {end}.', pic))

        elif mode == MODE_GANTI:
            user = params['user_baru']
            if pic.id_user_id == user.pk:
                rows.append(_row(key, jd, pics_by_jd, False, 'Sudah dipegang PIC baru.', pic))
            elif user.pk in holders:
                # The new PIC already holds this jenis data, so replacing the
                # old one in place would leave two open rows for the same user:
                # the old PIC is closed instead.
                end = max(today, pic.start_date)
                holders.discard(pic.id_user_id)
                rows.append(_row(key, jd, pics_by_jd, True,
                                 f'{user.username} sudah PIC aktif - PIC lama diakhiri per {end}.', pic))
            elif taken(jd.pk, user, pic.start_date):
                rows.append(_row(key, jd, pics_by_jd, False,
                                 f'Sudah ada PIC {user.username} dengan Tanggal Mulai {pic.start_date}.', pic))
            else:
                holders.discard(pic.id_user_id)
                holders.add(user.pk)
                rows.append(_row(key, jd, pics_by_jd, True, f'Ganti ke {_nama_user(user)}.', pic))

    return rows


def _public_rows(rows):
    return [{k: v for k, v in row.items() if not k.startswith('_')} for row in rows]


def _stamp(pic, username, today, created=False):
    if created:
        pic.create_by = username
        pic.create_date = today
    pic.update_by = username
    pic.update_date = today


def _apply(params, rows, request):
    """Carry out the actionable `rows`; return how many were applied."""
    now = timezone.now()
    today = timezone.now().date()
    username = (request.user.username or '')[:9]
    # Tiket actions are logged under the same account as the single-row views.
    admin_user = User.objects.filter(username='admin').first() or request.user
    tipe = params['tipe']
    role = _tiket_role_for(tipe)
    tipe_label = dict(PIC.TipePIC.choices).get(tipe, tipe)

    applied = 0
    for row in rows:
        if not row['ok']:
            continue
        jd, pic = row['_jd'], row['_pic']

        if params['mode'] == MODE_TAMBAH:
            new_pic = PIC(
                tipe=tipe, id_sub_jenis_data_ilap=jd,
                id_user=params['user_baru'], start_date=params['start_date'],
            )
            _stamp(new_pic, username, today, created=True)
            new_pic.save()
            if role:
                _assign_pic_to_open_tikets(new_pic.id_user, role, jd, tipe_label, admin_user, now)

        elif params['mode'] == MODE_HAPUS:
            _delete_pic_with_tikets(pic, admin_user, now)

        elif params['mode'] == MODE_AKHIRI:
            _propagate_pic_update(pic, pic.id_user, params['end_date'], admin_user, now)
            pic.end_date = params['end_date']
            _stamp(pic, username, today)
            pic.save()

        elif params['mode'] == MODE_GANTI:
            new_user = params['user_baru']
            # Hand-over on the tikets either way: the old user leaves the open
            # tikets and the new one is (re)assigned to them.
            _propagate_pic_update(pic, new_user, None, admin_user, now)
            already_active = PIC.objects.filter(
                tipe=tipe, id_sub_jenis_data_ilap=jd, id_user=new_user, end_date__isnull=True,
            ).exclude(pk=pic.pk).exists()
            if already_active:
                pic.end_date = max(today, pic.start_date)
            else:
                pic.id_user = new_user
            _stamp(pic, username, today)
            pic.save()

        applied += 1
    return applied


class PICBulkPemdaView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Page for bulk-editing PIC of a Pemda/Provinsi jenis data kode."""
    template_name = 'pic/bulk_pemda.html'
    raise_exception = True

    def test_func(self):
        return bool(_allowed_tipes(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tipes = _allowed_tipes(self.request.user)
        requested = (self.request.GET.get('tipe') or '').upper()
        labels = dict(PIC.TipePIC.choices)

        users = {}
        for tipe in tipes:
            qs = User.objects.filter(groups__name=_USER_GROUP[tipe], is_active=True).distinct()
            users[tipe] = sorted(
                ({'id': u.pk, 'text': _nama_user(u)} for u in qs),
                key=lambda item: item['text'].lower(),
            )

        context.update({
            'page_title': 'Bulk PIC Pemda/Provinsi',
            'tipes': [(tipe, labels[tipe]) for tipe in tipes],
            'default_tipe': requested if requested in tipes else tipes[0],
            'bulk_options': {
                'kode': _kode_options(),
                'users': users,
            },
        })
        return context


def _json_view(handler):
    """Wrap a bulk endpoint: permission check and uniform error responses."""
    def view(request):
        if not _allowed_tipes(request.user):
            return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
        try:
            return handler(request)
        except BulkPemdaError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    view.__name__ = handler.__name__
    view.__doc__ = handler.__doc__
    return view


@login_required
@require_GET
@_json_view
def pic_bulk_pemda_holders(request):
    """Who holds the PIC of `tipe` on a kode today, to pick the old PIC from."""
    tipe = request.GET.get('tipe')
    if tipe not in _allowed_tipes(request.user):
        raise BulkPemdaError('Anda tidak berwenang mengubah PIC untuk tipe ini.')
    kode = (request.GET.get('kode') or '').strip()
    scope = request.GET.get('scope') or 'ALL'
    if not _KODE_RE.match(kode) or scope not in SCOPE_PREFIXES:
        raise BulkPemdaError('Kode atau cakupan tidak valid.')

    jenis_data = _jenis_data_for(kode, scope)
    pics = PIC.objects.filter(tipe=tipe, id_sub_jenis_data_ilap__in=jenis_data).select_related('id_user')

    holders = {}
    covered = set()
    for pic in pics:
        entry = holders.setdefault(pic.id_user_id, {
            'id': pic.id_user_id, 'text': _nama_user(pic.id_user), 'aktif': 0, 'total': 0,
        })
        entry['total'] += 1
        if pic.end_date is None:
            entry['aktif'] += 1
            covered.add(pic.id_sub_jenis_data_ilap_id)

    total = jenis_data.count()
    return JsonResponse({
        'success': True,
        'total_jenis_data': total,
        'tanpa_pic_aktif': total - len(covered),
        'holders': sorted(holders.values(), key=lambda h: (-h['aktif'], h['text'].lower())),
    })


@login_required
@require_POST
@_json_view
def pic_bulk_pemda_preview(request):
    """What the bulk request would do per row - nothing is written."""
    params = _parse_params(request, request.POST)
    rows = _build_plan(params)
    ok = sum(1 for row in rows if row['ok'])
    return JsonResponse({
        'success': True,
        'total': len(rows),
        'total_ok': ok,
        'total_skip': len(rows) - ok,
        'rows': _public_rows(rows),
    })


@login_required
@require_POST
@_json_view
def pic_bulk_pemda_execute(request):
    """Apply the bulk request to the rows the admin kept ticked, atomically."""
    params = _parse_params(request, request.POST)
    selected = set(request.POST.getlist('selected'))
    if not selected:
        raise BulkPemdaError('Tidak ada baris yang dipilih.')

    with transaction.atomic():
        rows = _build_plan(params, selected=selected)
        applied = _apply(params, rows, request)

    skipped = len(rows) - applied
    message = f'{applied} PIC berhasil diproses.'
    if skipped:
        message += f' {skipped} baris dilewati.'
    return JsonResponse({
        'success': True,
        'applied': applied,
        'skipped': skipped,
        'message': message,
    })
