"""Sinkronisasi Tiket View - Admin PMDE pulls one tiket's QC data from Oracle.

Runs the rules of the tiket update sync (`sync_tiket_update`) for a single
tiket, straight from its detail page: the same Oracle query, the same field
comparison, the same status transitions and the same audit trail. See
docs/SYNC_TIKET_UPDATE_RULES.md.

For a tiket that is (or that the sync leaves) at Pengendalian Mutu or Selesai,
it also refreshes the rows per KD_TAHAP in the tiket's tabel I, as the
`sync_tiket_kd_tahap` command does for a whole year.
"""

import hashlib
import json
import logging
import uuid

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import formats
from django.views import View

from ...constants.tiket_action_types import ROLE_BADGES, TiketActionType, get_action_label
from ...constants.tiket_status import STATUS_BADGE_CLASSES, STATUS_LABELS
from ...models.tiket import Tiket
from ...models.tiket_pic import TiketPIC
from ...utils import format_number_with_separator
from ...utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError
from ...utils.tiket_dibatalkan import KOLOM_TARIKAN_DIBATALKAN
from ...utils.tiket_kd_tahap import (
    STATUS_KD_TAHAP,
    KdTahapError,
    ambil_kd_tahap_tiket,
    simpan_kd_tahap,
    tersimpan,
    urutkan,
)
from ..mixins import is_admin_pmde
from ..sync_tiket_update import (
    KOREKSI_JUDUL,
    TiketUpdateRowError,
    _active_pics_by_role,
    _apply_tiket_update_plan,
    _fetch_tiket_update_row,
    _plan_tanpa_rekap,
    _plan_tiket_update,
    notifikasi_penerima,
)

logger = logging.getLogger(__name__)

# Who writes the actions a correction removes (Aturan 2-5).
ACTION_ROLES = {
    TiketActionType.DIKEMBALIKAN: TiketPIC.Role.PIDE,
    TiketActionType.DIBATALKAN: TiketPIC.Role.P3DE,
    TiketActionType.DITRANSFER_KE_PMDE: TiketPIC.Role.PIDE,
    TiketActionType.PENGENDALIAN_MUTU: TiketPIC.Role.PMDE,
    TiketActionType.SELESAI: TiketPIC.Role.PMDE,
}

# Why each correction applies, shown with it in the preview.
KOREKSI_KETERANGAN = {
    'dibatalkan': (
        'Tiket dibatalkan oleh sinkronisasi (Aturan 4) karena rekap tarikan hanya berisi baris CDE, '
        'tetapi rekap Oracle kini berisi baris identifikasi.'
    ),
    'selesai': (
        'Tiket ditutup oleh sinkronisasi karena rekap tarikan menunjukkan Belum QC = 0, tetapi rekap '
        'Oracle untuk tarikan yang sama kini masih memiliki baris yang belum di-QC.'
    ),
}

# Why each rule fires, in the words of docs/SYNC_TIKET_UPDATE_RULES.md.
ATURAN_KETERANGAN = {
    1: 'Data sudah ditransfer ke PMDE dan ada baris identifikasi yang belum di-QC.',
    2: 'Seluruh baris identifikasi sudah di-QC (Belum QC = 0, Sudah QC = Baris I).',
    3: 'Data sudah ditransfer dan seluruh baris identifikasi sudah di-QC (Belum QC = 0, Sudah QC = Baris I).',
    4: 'Tarikan hanya berisi baris Res/CDE dan Res + CDE = Baris Lengkap: tiket dikembalikan PIDE dan dibatalkan.',
    5: 'Data sudah ditransfer tanpa baris identifikasi (hanya baris update).',
    6: 'PIDE sudah merekam data di Oracle (tgl_load).',
    7: 'PIDE sudah merekam dan mentransfer data ke PMDE di Oracle.',
    8: 'Oracle melakukan rematch dan ada baris baru yang belum di-QC.',
    9: 'PIDE merevisi tarikan dengan tanggal transfer baru yang berisi baris identifikasi.',
}


def _format_value(value):
    """Render a synced value for the preview table."""
    if value is None:
        return '-'
    if hasattr(value, 'hour'):
        return formats.date_format(value, 'd/m/Y H:i')
    return format_number_with_separator(value)


def _plan_fingerprint(plan):
    """Digest of what a plan writes, so a sync applies exactly what was previewed.

    Covers the Oracle row and every value the plan would write. Action
    timestamps are left out: the ones that fall back to "now" differ between
    the preview and the sync, and the rest are already in the row.
    """
    koreksi = plan['koreksi']
    payload = {
        'values': plan['values'],
        'status_from': plan['status_from'],
        'koreksi': koreksi and ([a.id for a in koreksi['actions']], koreksi['fields']),
        'field_changes': plan['field_changes'],
        'transitions': [(t['key'], t['status_to'], t['fields']) for t in plan['transitions']],
    }
    encoded = json.dumps(payload, default=str, sort_keys=True).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _fetch_row(tiket):
    """Fetch the tiket's Oracle row: (row or None, error message or None)."""
    try:
        service = OracleDataSyncService(connection_only=True)
        return _fetch_tiket_update_row(service, tiket.nomor_tiket), None
    except (OracleSyncConfigError, TiketUpdateRowError) as exc:
        return None, str(exc).strip()
    except Exception:
        logger.exception('Sinkronisasi tiket %s: gagal mengambil data Oracle', tiket.nomor_tiket)
        return None, 'Gagal mengambil data dari Oracle. Periksa koneksi Oracle.'


def _status_akhir(tiket, plan):
    """The tiket's status once the plan is applied."""
    if plan is None or not plan['changed']:
        return tiket.status_tiket
    if plan['transitions']:
        return plan['transitions'][-1]['status_to']
    if plan['koreksi']:
        return plan['koreksi']['fields']['status_tiket']
    return tiket.status_tiket


def _kd_tahap_plan(tiket, plan):
    """The tiket's rows per KD_TAHAP: stored now (`lama`) and in Oracle (`baru`).

    None when the tiket does not end at a status KD Tahap is kept for. An
    Oracle error is reported in `error` and leaves the rest of the sync be.
    """
    if _status_akhir(tiket, plan) not in STATUS_KD_TAHAP:
        return None
    lama = tersimpan(tiket)
    try:
        baru = ambil_kd_tahap_tiket(OracleDataSyncService(connection_only=True), tiket)
    except (KdTahapError, OracleSyncConfigError) as exc:
        return {'lama': lama, 'baru': None, 'changed': False, 'error': str(exc).strip()}
    except Exception:
        logger.exception('Sinkronisasi tiket %s: gagal mengambil KD Tahap', tiket.nomor_tiket)
        return {'lama': lama, 'baru': None, 'changed': False,
                'error': 'Gagal mengambil KD Tahap dari Oracle. Periksa koneksi Oracle.'}
    return {'lama': lama, 'baru': baru, 'changed': baru != lama, 'error': None}


def _kd_tahap_context(kd):
    """The KD Tahap part of the preview: totals, and only the rows that change."""
    if kd is None:
        return None
    rows = []
    if kd['changed']:
        for kd_tahap, _ in urutkan({**kd['lama'], **kd['baru']}):
            lama, baru = kd['lama'].get(kd_tahap), kd['baru'].get(kd_tahap)
            if lama != baru:
                rows.append({
                    'kd_tahap': kd_tahap if kd_tahap is not None else '-',
                    'lama': _format_value(lama),
                    'baru': _format_value(baru),
                })
    baru = kd['baru'] or {}
    return {
        'error': kd['error'],
        'changed': kd['changed'],
        'rows': rows,
        'jumlah_kd': len(baru),
        'total_lama': _format_value(sum(kd['lama'].values())),
        'total_baru': _format_value(sum(baru.values())),
    }


def _fingerprint(plan, kd):
    """Digest of everything a sync writes: the tiket update plan and the KD Tahap rows."""
    payload = {
        'plan': _plan_fingerprint(plan) if plan is not None and plan['changed'] else None,
        'kd_tahap': urutkan(kd['baru']) if kd is not None and kd['changed'] else None,
    }
    encoded = json.dumps(payload, default=str, sort_keys=True).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _sync_changed(plan, kd):
    return bool((plan is not None and plan['changed']) or (kd is not None and kd['changed']))


def _active_pics(tiket):
    return _active_pics_by_role(
        TiketPIC.objects.filter(id_tiket=tiket, active=True).select_related('id_user')
    )


def _preview_context(tiket, plan):
    """Turn a plan into the rows the preview modal shows."""
    tiket_pics = _active_pics(tiket)

    # Transitions can write fields the general update also writes
    # (tgl_transfer on Aturan 7); the latter's value is the one that lands.
    changes = {field: (old, new) for field, old, new in plan['field_changes']}
    for t in plan['transitions']:
        for field, new in t['fields'].items():
            if getattr(tiket, field) != new:
                changes.setdefault(field, (getattr(tiket, field), new))
    # The correction's fields, unless a transition then writes them anyway.
    koreksi = plan['koreksi']
    for field, new in (koreksi['fields'] if koreksi else {}).items():
        if field != 'status_tiket' and getattr(tiket, field) != new:
            changes.setdefault(field, (getattr(tiket, field), new))
    # A cancelled tiket's tarikan counts being cleared rather than synced. The
    # zeros among them (the migration carried 0 onto most tikets) are only
    # counted: the detail page never shows them, and listing a dozen "0 → -"
    # rows would bury the ones that matter.
    dikosongkan = {
        field: old for field, (old, new) in changes.items()
        if field in KOLOM_TARIKAN_DIBATALKAN and new is None
    }
    field_rows = [
        {
            'label': Tiket._meta.get_field(field).verbose_name,
            'old': _format_value(old),
            'new': _format_value(new),
        }
        for field, (old, new) in changes.items()
        if dikosongkan.get(field, None) != 0
    ]

    penerima = notifikasi_penerima(tiket_pics)
    transitions = []
    for t in plan['transitions']:
        actions = []
        for role, action, timestamp, catatan in t['actions']:
            pics = tiket_pics.get(role, [])
            user = pics[0].id_user if pics else None
            full_name = (user.get_full_name() or '').strip() if user else ''
            actions.append({
                'label': get_action_label(action),
                'role': ROLE_BADGES[role]['label'],
                'role_class': ROLE_BADGES[role]['class'],
                'user': (f'{user.username} - {full_name}' if full_name else user.username) if user else None,
                'timestamp': _format_value(timestamp),
                'catatan': catatan,
            })
        transitions.append({
            'aturan': t['aturan'],
            'keterangan': ATURAN_KETERANGAN[t['aturan']],
            'status_to': t['status_to'],
            'status_to_label': STATUS_LABELS.get(t['status_to'], '-'),
            'status_to_class': STATUS_BADGE_CLASSES.get(t['status_to'], 'bg-secondary'),
            'actions': actions,
            'notify_count': len(tiket_pics.get(TiketPIC.Role.P3DE, [])) if t['notify_p3de'] else 0,
            'notify_title': t['notify'][0],
            'notify_pic_count': len(penerima),
        })

    koreksi_actions = []
    for a in (koreksi['actions'] if koreksi else []):
        role = ACTION_ROLES.get(a.action)
        full_name = (a.id_user.get_full_name() or '').strip()
        koreksi_actions.append({
            'label': get_action_label(a.action),
            'role': ROLE_BADGES[role]['label'] if role else None,
            'role_class': ROLE_BADGES[role]['class'] if role else '',
            'user': f'{a.id_user.username} - {full_name}' if full_name else a.id_user.username,
            'timestamp': _format_value(a.timestamp),
            'catatan': a.catatan,
        })

    # With a correction, the transitions start from where it leaves the tiket.
    rules_from = koreksi['fields']['status_tiket'] if koreksi else plan['status_from']
    return {
        'field_rows': field_rows,
        'kosongkan': bool(dikosongkan),
        'kosongkan_nol': sum(1 for old in dikosongkan.values() if old == 0),
        'transitions': transitions,
        'koreksi_actions': koreksi_actions,
        'koreksi_judul': KOREKSI_JUDUL[koreksi['jenis']] if koreksi else None,
        'koreksi_keterangan': KOREKSI_KETERANGAN[koreksi['jenis']] if koreksi else None,
        'koreksi_notify_count': (
            len(tiket_pics.get(TiketPIC.Role.P3DE, [])) if koreksi and koreksi['notify_p3de'] else 0
        ),
        'status_manual_notify_count': len(penerima) if plan['notify_status_manual'] else 0,
        'res_cde_notify_count': (
            len(notifikasi_penerima(tiket_pics, (TiketPIC.Role.P3DE,))) if plan['notify_res_cde'] else 0
        ),
        'koreksi_to_label': STATUS_LABELS.get(rules_from, '-'),
        'koreksi_to_class': STATUS_BADGE_CLASSES.get(rules_from, 'bg-secondary'),
    }


class SinkronisasiTiketView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Preview and apply the Oracle tiket update sync for one tiket.

    GET  - fetch the tiket's row from Oracle and return the preview modal:
           the columns that would change, the status transition and the
           TiketAction records the sync would write.
    POST - fetch the row again and apply it, provided it still yields the
           plan the preview showed (`fingerprint`); otherwise nothing is
           written and the fresh preview is returned.

    Access Control:
    - Requires login
    - Admin PMDE only (`is_admin_pmde`: superuser, `admin`, `admin_pmde`)

    Side Effects on POST: exactly those of the bulk sync for this tiket - the
    Tiket fields and status, TiketAction records attributed to the tiket's
    active PICs, notifications to the active PIDE and PMDE PICs (and P3DE on
    Aturan 4 and on new Res/CDE counts) and a result CSV in sync_logs/.
    On a cancelled tiket it also clears the tarikan counts a cancel left
    behind (KOLOM_TARIKAN_DIBATALKAN), even when Oracle has no row for it.
    For a tiket that ends at Pengendalian Mutu or Selesai it also replaces the
    tiket's TiketKdTahap rows with the counts per KD_TAHAP in its tabel I
    (`_kd_tahap_plan`); a failure there is shown and the rest still syncs.
    Unlike the bulk sync it first corrects a tiket the sync cancelled
    (Aturan 4) or closed (Aturan 2, 3, 5) on a half-built rekap
    (`_plan_koreksi`): the sync's actions are deleted and the rules run again
    from the status before them.
    """

    template_name = 'tiket/sinkronisasi_tiket_modal_form.html'

    def test_func(self):
        return is_admin_pmde(self.request.user)

    def _render(self, tiket, row, error, plan, kd=None):
        context = {
            'tiket': tiket,
            'error': error,
            'not_found': error is None and row is None,
            'plan': plan,
            'kd_tahap': _kd_tahap_context(kd),
            'sync_changed': _sync_changed(plan, kd),
            'fingerprint': _fingerprint(plan, kd),
            'status_from_label': STATUS_LABELS.get(tiket.status_tiket, '-'),
            'status_from_class': STATUS_BADGE_CLASSES.get(tiket.status_tiket, 'bg-secondary'),
            'form_action': reverse('sinkronisasi_tiket', args=[tiket.pk]),
        }
        if plan is not None and plan['changed']:
            context.update(_preview_context(tiket, plan))
        return render_to_string(self.template_name, context, request=self.request)

    @staticmethod
    def _plan(tiket, row):
        # No rekap row: only a cancelled tiket's leftover counts to clear.
        if row is None:
            return _plan_tanpa_rekap(tiket)
        return _plan_tiket_update(tiket, row, koreksi=True)

    def get(self, request, pk):
        tiket = get_object_or_404(Tiket, pk=pk)
        row, error = _fetch_row(tiket)
        plan = self._plan(tiket, row) if error is None else None
        kd = _kd_tahap_plan(tiket, plan) if error is None else None
        return JsonResponse({'html': self._render(tiket, row, error, plan, kd)})

    def post(self, request, pk):
        tiket = get_object_or_404(Tiket, pk=pk)
        row, error = _fetch_row(tiket)
        if error is not None:
            return JsonResponse({
                'success': False,
                'message': error,
                'html': self._render(tiket, row, error, None),
            })
        # Fetched before the lock: the tabel I query is a full scan that can
        # take seconds. A status that moved meanwhile shows as a changed
        # fingerprint below.
        kd = _kd_tahap_plan(tiket, self._plan(tiket, row))

        with transaction.atomic():
            tiket = Tiket.objects.select_for_update().get(pk=pk)
            plan = self._plan(tiket, row)
            if _status_akhir(tiket, plan) not in STATUS_KD_TAHAP:
                kd = None
            if not _sync_changed(plan, kd):
                return JsonResponse({
                    'success': False,
                    'message': (
                        'Tiket tidak ditemukan di Oracle.' if row is None and kd is None
                        else 'Data tiket sudah sinkron dengan Oracle.'
                    ),
                    'html': self._render(tiket, row, None, plan, kd),
                })
            if request.POST.get('fingerprint') != _fingerprint(plan, kd):
                return JsonResponse({
                    'success': False,
                    'message': 'Data berubah sejak pratinjau dibuka. Periksa pratinjau terbaru lalu sinkronkan lagi.',
                    'html': self._render(tiket, row, None, plan, kd),
                })

            sync_id = str(uuid.uuid4())
            if plan['changed']:
                _apply_tiket_update_plan(tiket, plan, _active_pics(tiket), sync_id)
            if kd is not None and kd['changed']:
                simpan_kd_tahap(tiket, kd['baru'])

        logger.info(
            'Sinkronisasi tiket %s oleh %s (sync_id=%s): %d kolom, transisi %s, KD Tahap %s',
            tiket.nomor_tiket, request.user.username, sync_id, len(plan['field_changes']),
            [t['aturan'] for t in plan['transitions']] or '-',
            len(kd['baru']) if kd is not None and kd['changed'] else '-',
        )
        return JsonResponse({
            'success': True,
            'message': f'Tiket {tiket.nomor_tiket} berhasil disinkronkan dari Oracle.',
        })
