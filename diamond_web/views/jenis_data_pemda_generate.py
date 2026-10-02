"""Generate one Pemda/Provinsi jenis data for every PD/PV ILAP that lacks it.

A Pemda/Provinsi jenis data carries the same 4-digit kode at every pemda (see
`utils.pemda_kode`), so adding e.g. ``4101`` by hand means one create per
pemda, each with its ids typed from scratch. This page derives the ids from
the kode for every PD/PV ILAP in scope that does not have it yet and fills them
with one shared description.

The flow is template -> preview -> confirm -> result, and nothing is written
before the confirm:

- `jenis_data_pemda_template` suggests the description from the rows that
  already carry the kode (the most common value of each field).
- `jenis_data_pemda_preview` lists, per ILAP, the ids that would be created and
  why any ILAP is left out.
- `jenis_data_pemda_execute` rebuilds that plan for the ILAPs the admin kept
  ticked and creates them in one transaction, so a code created meanwhile by
  someone else is skipped rather than duplicated.
"""
import re
from collections import Counter

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView

from ..models.ilap import ILAP
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.jenis_tabel import JenisTabel
from ..models.status_data import StatusData
from ..utils.pemda_kode import (
    SCOPE_PREFIXES,
    is_valid_kode,
    jenis_data_for_kode,
    kode_ids,
    kode_options,
    pemda_filter,
)
from .mixins import AdminP3DERequiredMixin

_ILAP_CODE_RE = re.compile(r'^P[DV]\d{3}$')
# Only ILAPs named as a region get pemda jenis data: a PD/PV row that is not a
# kabupaten, kota or provinsi (e.g. a placeholder named just "PD908") is not a
# pemda. Whole words, so "Kotawaringin" does not pass for "kota".
_WILAYAH_RE = re.compile(r'\b(kabupaten|kota|provinsi)\b', re.IGNORECASE)
# DKI Jakarta reports as a province, not per pemda, so it is left out too.
_JAKARTA_RE = re.compile(r'jakarta', re.IGNORECASE)
_MAX_NAMA = 255
_VARIANT_LIMIT = 8

STATUS_BARU = 'baru'
STATUS_PERINGATAN = 'peringatan'


class GenerateError(Exception):
    """A request the admin has to correct; its message is shown as-is."""


def _is_admin_p3de(user):
    # Same gate as the Jenis Data ILAP list and its create view.
    return user.is_authenticated and user.groups.filter(name__in=['admin', 'admin_p3de']).exists()


def _norm(text):
    return ' '.join((text or '').split()).upper()


def _parse_kode_scope(data):
    kode = (data.get('kode') or '').strip()
    if not is_valid_kode(kode):
        raise GenerateError('Kode jenis data harus 4 digit (01-99 + 01-99), misalnya 4101.')
    scope = data.get('scope') or 'ALL'
    if scope not in SCOPE_PREFIXES:
        raise GenerateError('Cakupan tidak valid.')
    # Mirrors the dropdown: a kode carried only by excluded ILAPs is theirs, not
    # a pemda jenis data, so it cannot be pushed through by typing or posting it.
    carriers = [jd.id_ilap for jd in jenis_data_for_kode(kode, 'ALL')]
    if carriers and all(_exclusion_reason(ilap) for ilap in carriers):
        names = ', '.join(sorted({f'{i.id_ilap} {i.nama_ilap}' for i in carriers}))
        raise GenerateError(
            f'Kode {kode} hanya dipakai ILAP yang dikecualikan ({names}), '
            f'jadi tidak bisa digenerate ke pemda lain.'
        )
    return kode, scope


def _parse_text(data, field, label, required):
    value = ' '.join((data.get(field) or '').split())
    if required and not value:
        raise GenerateError(f'{label} wajib diisi.')
    if len(value) > _MAX_NAMA:
        raise GenerateError(f'{label} maksimal {_MAX_NAMA} karakter.')
    return value


def _parse_params(data):
    kode, scope = _parse_kode_scope(data)
    params = {
        'kode': kode,
        'scope': scope,
        'nama_jenis_data': _parse_text(data, 'nama_jenis_data', 'Nama Jenis Data', True),
        'nama_sub_jenis_data': _parse_text(data, 'nama_sub_jenis_data', 'Nama Sub Jenis Data', True),
        'nama_tabel_I': _parse_text(data, 'nama_tabel_I', 'Nama Tabel I', False),
        'nama_tabel_U': _parse_text(data, 'nama_tabel_U', 'Nama Tabel U', False),
    }
    try:
        params['jenis_tabel'] = JenisTabel.objects.get(pk=int(data.get('id_jenis_tabel')))
    except (JenisTabel.DoesNotExist, TypeError, ValueError):
        raise GenerateError('Jenis Tabel wajib dipilih.')
    params['status_data'] = None
    if data.get('id_status_data'):
        try:
            params['status_data'] = StatusData.objects.get(pk=int(data['id_status_data']))
        except (StatusData.DoesNotExist, ValueError):
            raise GenerateError('Status Data tidak ditemukan.')
    return params


def _pemda_ilaps(scope):
    return ILAP.objects.filter(pemda_filter(SCOPE_PREFIXES[scope], field='id_ilap')).order_by('id_ilap')


def _exclusion_reason(ilap):
    """Why `ilap` must not get generated jenis data, or None when it may."""
    nama = ilap.nama_ilap or ''
    if not _ILAP_CODE_RE.match(ilap.id_ilap or ''):
        return 'kode ILAP tidak berpola PD/PV + 3 digit'
    if not _WILAYAH_RE.search(nama):
        return 'nama tidak mengandung Kabupaten/Kota/Provinsi'
    if _JAKARTA_RE.search(nama):
        return 'wilayah DKI Jakarta'
    return None


def _split_ilaps(scope):
    """(eligible ILAPs, excluded ILAPs as display strings) within `scope`."""
    eligible, excluded = [], []
    for ilap in _pemda_ilaps(scope):
        reason = _exclusion_reason(ilap)
        if reason:
            excluded.append(f'{ilap.id_ilap} - {ilap.nama_ilap} ({reason})')
        else:
            eligible.append(ilap)
    return eligible, excluded


def _build_plan(params, selected=None):
    """Per PD/PV ILAP in scope: create, create-with-warning, or skip.

    Returns ``(rows, summary)``. `rows` holds only ILAPs that would get a new
    row; ILAPs that already carry the kode, or that `_exclusion_reason`
    rules out, are only reported in `summary`. `selected` (a set of row keys)
    narrows the plan before it is worked out.
    """
    kode = params['kode']
    ilaps, dikecualikan = _split_ilaps(params['scope'])

    targets = []
    for ilap in ilaps:
        id_jenis, id_sub = kode_ids(ilap.id_ilap, kode)
        targets.append((f'ilap-{ilap.pk}', ilap, id_jenis, id_sub))

    existing_sub = set(
        JenisDataILAP.objects.filter(id_sub_jenis_data__in=[t[3] for t in targets])
        .values_list('id_sub_jenis_data', flat=True)
    )
    # The first two digits of the kode are the jenis data, which an ILAP may
    # already hold under another sub (e.g. 5701 when generating 5702).
    jenis_names = {}
    for id_jenis, nama in (
        JenisDataILAP.objects.filter(id_jenis_data__in=[t[2] for t in targets])
        .values_list('id_jenis_data', 'nama_jenis_data')
    ):
        jenis_names.setdefault(id_jenis, set()).add(nama)

    wanted = _norm(params['nama_jenis_data'])
    rows, sudah_ada = [], []
    dilewati_terpilih = 0
    for key, ilap, id_jenis, id_sub in targets:
        if id_sub in existing_sub:
            sudah_ada.append(f'{ilap.id_ilap} - {ilap.nama_ilap} ({id_sub})')
            if selected is not None and key in selected:
                dilewati_terpilih += 1
            continue
        if selected is not None and key not in selected:
            continue
        names = jenis_names.get(id_jenis, set())
        if names and wanted not in {_norm(n) for n in names}:
            status = STATUS_PERINGATAN
            keterangan = (
                f'ID Jenis Data {id_jenis} sudah dipakai ILAP ini dengan nama '
                f'"{sorted(names)[0]}", berbeda dari nama yang akan diisi.'
            )
        else:
            status = STATUS_BARU
            keterangan = ''
        rows.append({
            'key': key,
            'id_ilap': ilap.id_ilap,
            'nama_ilap': ilap.nama_ilap,
            'id_jenis_data': id_jenis,
            'id_sub_jenis_data': id_sub,
            'status': status,
            'keterangan': keterangan,
            '_ilap': ilap,
        })

    summary = {
        'total_ilap': len(ilaps) + len(dikecualikan),
        'total_baru': sum(1 for r in rows if r['status'] == STATUS_BARU),
        'total_peringatan': sum(1 for r in rows if r['status'] == STATUS_PERINGATAN),
        'total_sudah_ada': len(sudah_ada),
        'sudah_ada': sudah_ada,
        'dikecualikan': dikecualikan,
        # Ticked ILAPs that already carry the kode - on execute, ones that got
        # it between preview and confirm.
        'dilewati_terpilih': dilewati_terpilih,
    }
    return rows, summary


def _generate_kode_options(eligible):
    """Existing kodes with how many `eligible` ILAPs still lack them, per prefix.

    `belum_PD` / `belum_PV` are what a generate in that scope would create. The
    page only offers a kode whose count in the chosen scope is above zero - one
    every eligible ILAP already carries has nothing left to generate.

    Returns ``(options, excluded_only)``. A kode no eligible ILAP carries - it
    exists only at ILAPs `_exclusion_reason` rules out, e.g. a DKI Jakarta
    DPMPTSP dataset - belongs to those ILAPs and is not spread to the pemda,
    so it goes to `excluded_only` instead of `options`.
    """
    eligible_codes = {ilap.id_ilap for ilap in eligible}
    total = Counter(code[:2] for code in eligible_codes)
    carried = Counter(
        (code[-4:], code[:2])
        for code in JenisDataILAP.objects.filter(pemda_filter(SCOPE_PREFIXES['ALL']))
        .values_list('id_sub_jenis_data', flat=True)
        if code[:5] in eligible_codes
    )
    options, excluded_only = [], []
    for opt in kode_options():
        if not is_valid_kode(opt['kode']):
            continue
        if not carried[(opt['kode'], 'PD')] + carried[(opt['kode'], 'PV')]:
            excluded_only.append(opt['kode'])
            continue
        opt['belum_PD'] = total['PD'] - carried[(opt['kode'], 'PD')]
        opt['belum_PV'] = total['PV'] - carried[(opt['kode'], 'PV')]
        options.append(opt)
    return options, excluded_only


def _public_rows(rows):
    return [{k: v for k, v in row.items() if not k.startswith('_')} for row in rows]


def _json_view(handler):
    """Wrap an endpoint: admin P3DE gate and uniform error responses."""
    def view(request):
        if not _is_admin_p3de(request.user):
            return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
        try:
            return handler(request)
        except GenerateError as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    view.__name__ = handler.__name__
    view.__doc__ = handler.__doc__
    return view


class JenisDataPemdaGenerateView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    """Page for generating one PD/PV jenis data kode across all pemda."""
    template_name = 'jenis_data_ilap/generate_pemda.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        eligible, excluded = _split_ilaps('ALL')
        counts = Counter(ilap.id_ilap[:2] for ilap in eligible)
        kode_list, excluded_only = _generate_kode_options(eligible)
        context.update({
            'page_title': 'Generate Jenis Data PD/PV',
            'jenis_tabel_list': JenisTabel.objects.all(),
            'status_data_list': StatusData.objects.all(),
            'total_ilap_pd': counts['PD'],
            'total_ilap_pv': counts['PV'],
            'total_ilap_dikecualikan': len(excluded),
            'generate_options': {
                'kode': kode_list,
                'kode_dikecualikan': excluded_only,
                'total': {'PD': counts['PD'], 'PV': counts['PV']},
            },
        })
        return context


@require_GET
@_json_view
def jenis_data_pemda_template(request):
    """Suggested description for a kode, from the PD/PV rows that already carry it."""
    kode, scope = _parse_kode_scope(request.GET)
    # Descriptions are shared by PD and PV, so suggest from both whatever the scope.
    existing = list(jenis_data_for_kode(kode, 'ALL'))

    def common(field, limit=1):
        counter = Counter(getattr(jd, field) for jd in existing if getattr(jd, field) not in (None, ''))
        return counter.most_common(limit)

    def first(field):
        top = common(field)
        return top[0][0] if top else ''

    eligible, excluded = _split_ilaps(scope)
    existing_codes = {jd.id_sub_jenis_data for jd in existing}
    belum_ada = sum(1 for ilap in eligible if kode_ids(ilap.id_ilap, kode)[1] not in existing_codes)
    return JsonResponse({
        'success': True,
        'kode_baru': not existing,
        'sudah_ada_pd': sum(1 for jd in existing if jd.id_sub_jenis_data.startswith('PD')),
        'sudah_ada_pv': sum(1 for jd in existing if jd.id_sub_jenis_data.startswith('PV')),
        'ilap_in_scope': len(eligible),
        'belum_ada_in_scope': belum_ada,
        'dikecualikan_in_scope': len(excluded),
        'defaults': {
            'nama_jenis_data': first('nama_jenis_data'),
            'nama_sub_jenis_data': first('nama_sub_jenis_data'),
            'nama_tabel_I': first('nama_tabel_I'),
            'nama_tabel_U': first('nama_tabel_U'),
            'id_jenis_tabel': first('id_jenis_tabel_id'),
            'id_status_data': first('id_status_data_id'),
        },
        'variants': {
            field: [{'value': v, 'count': n} for v, n in common(field, _VARIANT_LIMIT)]
            for field in ('nama_jenis_data', 'nama_sub_jenis_data')
        },
    })


@require_POST
@_json_view
def jenis_data_pemda_preview(request):
    """What the generator would create per ILAP - nothing is written."""
    params = _parse_params(request.POST)
    rows, summary = _build_plan(params)
    return JsonResponse({'success': True, 'rows': _public_rows(rows), **summary})


@require_POST
@_json_view
def jenis_data_pemda_execute(request):
    """Create the kode for the ILAPs the admin kept ticked, atomically."""
    params = _parse_params(request.POST)
    selected = set(request.POST.getlist('selected'))
    if not selected:
        raise GenerateError('Tidak ada ILAP yang dipilih.')

    today = timezone.now().date()
    username = (request.user.username or '')[:9]
    created = []
    with transaction.atomic():
        rows, summary = _build_plan(params, selected=selected)
        for row in rows:
            jd = JenisDataILAP.objects.create(
                id_ilap=row['_ilap'],
                id_jenis_data=row['id_jenis_data'],
                id_sub_jenis_data=row['id_sub_jenis_data'],
                nama_jenis_data=params['nama_jenis_data'],
                nama_sub_jenis_data=params['nama_sub_jenis_data'],
                nama_tabel_I=params['nama_tabel_I'],
                nama_tabel_U=params['nama_tabel_U'],
                id_jenis_tabel=params['jenis_tabel'],
                id_status_data=params['status_data'],
                create_date=today, create_by=username,
                update_date=today, update_by=username,
            )
            created.append({
                'id_sub_jenis_data': jd.id_sub_jenis_data,
                'id_jenis_data': jd.id_jenis_data,
                'id_ilap': row['id_ilap'],
                'nama_ilap': row['nama_ilap'],
                'profil_url': reverse('jenis_data_ilap_profil', args=[jd.id_sub_jenis_data]),
            })

    skipped = summary['dilewati_terpilih']
    message = f'{len(created)} jenis data berhasil dibuat untuk kode {params["kode"]}.'
    if skipped:
        message += f' {skipped} ILAP dilewati karena kodenya sudah ada.'
    return JsonResponse({
        'success': True,
        'kode': params['kode'],
        'created': created,
        'skipped': skipped,
        'message': message,
    })
