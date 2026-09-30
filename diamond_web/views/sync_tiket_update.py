"""Tiket update sync from Oracle — updates QC columns & status transitions.

This module provides the core logic to:
1. Query Oracle for updated QC/transfer columns (baris_i, baris_u, baris_res,
   baris_cde, tgl_transfer, tgl_rematch, sudah_qc, belum_qc, lolos_qc,
   tidak_lolos_qc, and all qc_* columns).
2. Update matching local Tiket records.
3. Apply status transitions with proper TiketAction audit trail:
   - DIKIRIM_KE_PIDE (4) + local tgl_rekam_pide null + tgl_transfer null
     → IDENTIFIKASI (5) (records tgl_rekam_pide from Oracle tgl_load)
   - DIKIRIM_KE_PIDE (4) + local tgl_rekam_pide null + tgl_transfer not null
     → PENGENDALIAN_MUTU (6) (records tgl_rekam_pide & tgl_transfer)
   - IDENTIFIKASI (5) + tgl_transfer not null + baris_i > 0
     → PENGENDALIAN_MUTU (6)
   - PENGENDALIAN_MUTU (6) + QC complete → SELESAI (8)
   - IDENTIFIKASI (5) + tgl_transfer not null + QC complete
     → SELESAI (8) (direct)
     (QC complete: belum_qc == 0, sudah_qc == baris_i and the rows are not
     CDE only — see _qc_lengkap)
   - IDENTIFIKASI (5) + tgl_transfer not null + i=0 & u=0 & res=0 & cde>0
     → DIBATALKAN (7) (dikembalikan by PIDE, with notification to P3DE)
   - IDENTIFIKASI (5) + tgl_transfer not null + belum_qc != 0
     + (i=0 & u>0) OR (i=0 & u=0 & res>0 & cde=0)
     → SELESAI (8) (direct, baris-based)
   - SELESAI (8) + tgl_rematch not null + belum_qc > 0
     → PENGENDALIAN_MUTU (6) (rematch reopens QC, timestamped tgl_rematch)
   - SELESAI (8) + tgl_rematch null + tgl_transfer changed + baris_i > 0
     + belum_qc != 0 → PENGENDALIAN_MUTU (6) (PIDE revised the tarikan)

See docs/SYNC_TIKET_UPDATE_RULES.md for full documentation.
"""

import copy
import json
import logging
import uuid
import os
import csv
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, FileResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.core.cache import cache
from django.db import connection as db_connection
from django.db.models import Max
from django.conf import settings
from django.urls import reverse

from ..models.tiket import Tiket
from ..models.tiket_action import TiketAction
from ..models.tiket_pic import TiketPIC
from ..constants.tiket_action_types import TiketActionType, get_action_label
from ..constants.tiket_status import (
    STATUS_LABELS,
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
    STATUS_DIBATALKAN,
)
from ..models.notification import Notification
from ..utils import lift_time_above
from ..utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError
from ..tasks import check_tiket_update_data_task, sync_tiket_update_data_task

logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
SYNC_LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sync_logs'
)
os.makedirs(SYNC_LOGS_DIR, exist_ok=True)

# Oracle query to fetch tiket update data (QC columns and transfer dates).
# {filter} narrows the raw rows before they are aggregated: empty for the full
# sync, a no_tiket filter when a single tiket is synchronised from its page.
_TIKET_UPDATE_ORACLE_SQL_TEMPLATE = """
    SELECT
        DISTINCT
        CASE 
            WHEN LENGTH(no_tiket) = 16 AND SUBSTR(no_tiket,1,1) = 'E' THEN SUBSTR(no_tiket, 1, 1) || 'I' || SUBSTR(no_tiket, 2)
            ELSE no_tiket 
        END nomor_tiket,
        b.tgl_load tgl_rekam_pide,
        COALESCE(b.JML_LOG, 0) baris_i,
        COALESCE(b.JML_LOG_U, 0) baris_u,
        COALESCE(b.JML_RES, 0) baris_res,
        COALESCE(b.JML_CDE, 0) baris_cde,
        b.tgl_transfer,
        b.TGL_REMATCH tgl_rematch,
        CASE WHEN b.belum_qc = 0 THEN b.tgl_qc ELSE NULL END tgl_close_tiket,
        COALESCE(b.SUDAH_QC, 0) SUDAH_QC,
        COALESCE(b.belum_qc, 0) belum_qc,
        COALESCE(b.lolos_qc, 0) lolos_qc,
        COALESCE(b.TIDAK_LOLOS_QC, 0) tidak_lolos_qc,
        COALESCE(b.QC_P, 0) QC_P,
        COALESCE(b.QC_X, 0) QC_X,
        COALESCE(b.QC_W, 0) QC_W,
        COALESCE(b.QC_F, 0) QC_F,
        COALESCE(b.QC_A, 0) QC_A,
        COALESCE(b.QC_C, 0) QC_C,
        COALESCE(b.QC_N, 0) QC_N,
        COALESCE(b.QC_Y, 0) QC_Y,
        COALESCE(b.QC_Z, 0) QC_Z,
        COALESCE(b.QC_U, 0) QC_U,
        COALESCE(b.QC_E, 0) QC_E,
        COALESCE(b.QC_V, 0) QC_V,
        COALESCE(b.QC_R, 0) QC_R,
        COALESCE(b.QC_D, 0) QC_D
    FROM
        (
        SELECT
            no_tiket,
            min(tgl_load) tgl_load,
            MIN(tgl_transfer) tgl_transfer,
            MAX(tgl_rematch) tgl_rematch,
            MAX(tgl_qc) tgl_qc,
            SUM(JML_LOG) JML_LOG,
            SUM(JML_LOG_U) JML_LOG_U,
            SUM(JML_RES) JML_RES,
            SUM(JML_CDE) JML_CDE,
            SUM(SUDAH_QC) SUDAH_QC,
            SUM(belum_qc) belum_qc,
            SUM(lolos_qc) lolos_qc,
            SUM(TIDAK_LOLOS_QC) TIDAK_LOLOS_QC,
            SUM(QC_P) QC_P,
            SUM(QC_X) QC_X,
            SUM(QC_W) QC_W,
            SUM(QC_F) QC_F,
            SUM(QC_A) QC_A,
            SUM(QC_C) QC_C,
            SUM(QC_N) QC_N,
            SUM(QC_Y) QC_Y,
            SUM(QC_Z) QC_Z,
            SUM(QC_U) QC_U,
            SUM(QC_E) QC_E,
            SUM(QC_V) QC_V,
            SUM(QC_R) QC_R,
            SUM(QC_D) QC_D
        FROM
            PVPTD.ZA_REKAP_TARIKAN
        {filter}
        GROUP BY
            no_tiket
    ) b
"""
_TIKET_UPDATE_ORACLE_SQL = _TIKET_UPDATE_ORACLE_SQL_TEMPLATE.format(filter='')

# The Oracle columns the sync copies onto the local tiket, in the order it
# compares them. The two dates are copied even when Oracle has NULL; the counts
# only when Oracle returns a value.
_SYNC_DATE_FIELDS = ('tgl_transfer', 'tgl_rematch')
_SYNC_COUNT_FIELDS = (
    'baris_i', 'baris_u', 'baris_res', 'baris_cde',
    'sudah_qc', 'belum_qc', 'lolos_qc', 'tidak_lolos_qc',
    'qc_p', 'qc_x', 'qc_w', 'qc_f', 'qc_a', 'qc_c', 'qc_n',
    'qc_y', 'qc_z', 'qc_u', 'qc_e', 'qc_v', 'qc_r', 'qc_d',
)


# Catatan of the two actions Aturan 4 writes; they mark a return as the sync's.
CATATAN_DIKEMBALIKAN_AUTO_SYNC = 'Tiket dikembalikan oleh PIDE (auto-sync)'
CATATAN_DIBATALKAN_AUTO_SYNC = 'Tiket dibatalkan (dikembalikan oleh PIDE: auto-sync)'
_AUTO_SYNC_RETURN = {
    (TiketActionType.DIKEMBALIKAN, CATATAN_DIKEMBALIKAN_AUTO_SYNC),
    (TiketActionType.DIBATALKAN, CATATAN_DIBATALKAN_AUTO_SYNC),
}

# Catatan of the actions the sync writes when it closes a tiket. Aturan 2's
# SELESAI carries a stray ")" that Aturan 3 and 5 do not: it is kept as is,
# because it is what tells the two closes apart in trails already written.
CATATAN_DITRANSFER = 'Tiket ditransfer ke PMDE'
CATATAN_PENGENDALIAN_MUTU = 'Tiket selesai pengendalian mutu'
CATATAN_SELESAI_ATURAN_2 = 'Tiket selesai diproses)'
CATATAN_SELESAI = 'Tiket selesai diproses'

# Actions that record a step of the tiket workflow. Isian edits, PIC changes
# and the like can follow a sync's actions without making them any less the
# tiket's latest step.
_STATUS_ACTIONS = {
    TiketActionType.DIREKAM, TiketActionType.DITELITI, TiketActionType.DIKEMBALIKAN,
    TiketActionType.DIKIRIM_KE_PIDE, TiketActionType.IDENTIFIKASI,
    TiketActionType.PENGENDALIAN_MUTU, TiketActionType.DIBATALKAN,
    TiketActionType.SELESAI, TiketActionType.DITRANSFER_KE_PMDE, TiketActionType.REMATCH,
}


# How the preview and the result CSV name each correction (`_plan_koreksi`).
KOREKSI_JUDUL = {
    'dibatalkan': 'Koreksi Pembatalan',
    'selesai': 'Koreksi Penutupan',
}

def _hanya_cde(baris_i, baris_u, baris_res, baris_cde):
    """True when PIDE found nothing but CDE rows in the tarikan (Aturan 4).

    Such a tiket always has belum_qc == 0 because it has nothing to QC, not
    because QC is finished — so Aturan 2 and 3 must not read it as complete.
    """
    return (
        baris_i is not None and baris_i == 0
        and baris_u is not None and baris_u == 0
        and baris_res is not None and baris_res == 0
        and baris_cde is not None and baris_cde > 0
    )


def _qc_lengkap(baris_i, baris_u, baris_res, baris_cde, sudah_qc, belum_qc):
    """True when the rekap shows QC finished, so Aturan 2 and 3 may close.

    belum_qc == 0 alone is not enough. When PVPTD.ZA_REKAP_TARIKAN is only
    partly built, a tiket's I rows or QC counts can be missing, and belum_qc
    reads 0 while QC is still open. A complete rekap always has
    sudah_qc + belum_qc == baris_i (only I rows are QC'd), so with nothing
    left, every I row must be QC'd. A tarikan of CDE rows alone has nothing
    to QC and is Aturan 4's.
    """
    return (
        belum_qc is not None and belum_qc == 0
        and sudah_qc == baris_i
        and not _hanya_cde(baris_i, baris_u, baris_res, baris_cde)
    )


def _plan_koreksi(tiket, values):
    """Undo a cancel or close by the sync that the Oracle rekap no longer bears out.

    When PVPTD.ZA_REKAP_TARIKAN is only partly built, the sync can read a
    tarikan wrongly, and no rule leads out of the status it then sets:

    - Dibatalkan: the tarikan read as CDE rows alone, so Aturan 4 cancelled
      the tiket. The rekap now holds I/U/Res rows.
    - Selesai: belum_qc read 0, so Aturan 2 (or 3/5, from Identifikasi)
      closed the tiket. The rekap now has rows left to QC for the same
      tarikan: tgl_transfer unchanged and no rematch, which Aturan 8 and 9
      would handle.

    Applies only while the tiket's latest workflow actions are exactly the
    ones the sync wrote, so nothing anyone did afterwards is undone. *values*
    is the plan's Oracle row, dates already made DB-safe.

    Returns None, or a dict with:
        jenis: 'dibatalkan' or 'selesai'
        actions: the sync's actions to delete, oldest first
        fields: the tiket fields as they stood before, status included
        notify_p3de: message for the tiket's P3DE PICs, or None
    """
    if tiket.status_tiket == STATUS_DIBATALKAN:
        if not any(values.get(f) for f in ('baris_i', 'baris_u', 'baris_res')):
            return None
    elif tiket.status_tiket == STATUS_SELESAI:
        belum_qc = values.get('belum_qc')
        if not (
            belum_qc is not None and belum_qc > 0
            and values['tgl_rematch'] is None
            and values['tgl_transfer'] is not None
            and values['tgl_transfer'] == tiket.tgl_transfer
        ):
            return None
    else:
        return None

    trail = [
        a for a in TiketAction.objects.filter(id_tiket=tiket).select_related('id_user').order_by('-id')
        if a.action in _STATUS_ACTIONS
    ]

    if tiket.status_tiket == STATUS_DIBATALKAN:
        pair = []
        for action in trail:
            if (action.action, action.catatan) not in _AUTO_SYNC_RETURN:
                break
            pair.append(action)
        if not pair:
            return None
        earlier = trail[len(pair):]

        def latest(action_type):
            return next((a.timestamp for a in earlier if a.action == action_type), None)

        return {
            'jenis': 'dibatalkan',
            'actions': pair[::-1],
            'fields': {
                'status_tiket': STATUS_IDENTIFIKASI,
                'tgl_rekam_pide': values.get('tgl_rekam_pide') or latest(TiketActionType.IDENTIFIKASI),
                'tgl_dikembalikan': latest(TiketActionType.DIKEMBALIKAN),
            },
            'notify_p3de': (
                f'Tiket {tiket.nomor_tiket} tidak jadi dibatalkan: rekap tarikan Oracle kini '
                f'berisi baris identifikasi.'
            ),
        }

    def is_(action, action_type, catatan):
        return action is not None and action.action == action_type and action.catatan == catatan

    selesai, pm, ditransfer = (trail + [None, None, None])[:3]
    if not is_(pm, TiketActionType.PENGENDALIAN_MUTU, CATATAN_PENGENDALIAN_MUTU):
        return None
    if is_(selesai, TiketActionType.SELESAI, CATATAN_SELESAI_ATURAN_2):
        # Aturan 2 closed it from Pengendalian Mutu.
        actions, status = [pm, selesai], STATUS_PENGENDALIAN_MUTU
    elif is_(selesai, TiketActionType.SELESAI, CATATAN_SELESAI):
        # Aturan 3 or 5 closed it from Identifikasi, writing the transfer in
        # the same run (unless the tiket had no active PIDE PIC).
        actions, status = [pm, selesai], STATUS_IDENTIFIKASI
        if is_(ditransfer, TiketActionType.DITRANSFER_KE_PMDE, CATATAN_DITRANSFER)                 and ditransfer.timestamp == pm.timestamp:
            actions.insert(0, ditransfer)
    else:
        return None
    return {
        'jenis': 'selesai',
        'actions': actions,
        'fields': {'status_tiket': status},
        'notify_p3de': None,
    }


def dikembalikan_timestamp(tiket, tgl_transfer):
    """When Aturan 4 stamps the return: ``tgl_transfer``, kept after the trail.

    Oracle's tgl_transfer is date-only (00:00), so on the day PIDE recorded
    the data it lands before the IDENTIFIKASI action and the return reads as
    preceding it. The day is right; only the time is borrowed, so it is lifted
    just past the tiket's latest action, as same-day form dates are.
    """
    latest = TiketAction.objects.filter(id_tiket=tiket).aggregate(m=Max('timestamp'))['m']
    return lift_time_above(tgl_transfer, latest)


def _is_admin_user(user):
    """Check if the given user is an admin user."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name='admin').exists()


@login_required
@user_passes_test(_is_admin_user)
@require_GET
def sync_tiket_update_page(request):
    """Render the Oracle tiket update (tarikan) sync page."""
    return render(request, 'oracle_sync/tiket_update.html')


def _make_aware_datetime(dt):
    """Return a datetime safe for DB storage respecting USE_TZ setting."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if settings.USE_TZ:
            if timezone.is_naive(dt):
                return timezone.make_aware(dt)
            return dt
        else:
            if timezone.is_aware(dt):
                return dt.replace(tzinfo=None)
            return dt
    return dt


def _ensure_naive_datetimes(data: dict) -> dict:
    """Return a copy of *data* with all datetime values coerced to timezone-naive."""
    if settings.USE_TZ:
        return data
    out = dict(data)
    for k, v in out.items():
        if isinstance(v, datetime) and timezone.is_aware(v):
            out[k] = v.replace(tzinfo=None)
    return out


def _log_failed_row(sync_id, nomor_tiket, error_msg, row_number=None):
    """Log a failed row to a CSV file for review and debugging."""
    try:
        log_filename = os.path.join(SYNC_LOGS_DIR, f'tiket_update_failed_rows_{sync_id}.csv')
        file_exists = os.path.exists(log_filename)

        with open(log_filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    'Timestamp', 'Row Number', 'Nomor Tiket', 'Error Reason'
                ])
            writer.writerow([
                timezone.now().isoformat(),
                row_number or '-',
                nomor_tiket or '-',
                error_msg or 'Unknown error'
            ])
        logger.debug(f"Failed row logged to {log_filename}")
    except Exception as e:
        logger.error(f"Failed to log error row: {str(e)}")


def _log_update_result_row(sync_id, nomor_tiket, kategori, detail=''):
    """Log a tiket update result row to a comprehensive CSV file.

    Kategori can be one of:
        - 'Baris Diupdate'       — row data was updated
        - 'Belum Disinkronisasi' — tiket nomor not found in local DB
        - 'Status → Pengendalian Mutu' — status transition to PMDE
        - 'Status → Pengendalian Mutu (rematch)' — reopened from Selesai
        - 'Status → Pengendalian Mutu (transfer ulang)' — reopened from Selesai
          because PIDE revised the tarikan and baris_i is now > 0
        - 'Status → Selesai'     — status transition to Selesai
        - 'Tidak Berubah'        — no changes detected
        - 'Error'                — processing error

    The CSV contains one row per tiket per category so each tiket may
    appear multiple times if it falls into several categories.
    """
    try:
        log_filename = os.path.join(SYNC_LOGS_DIR, f'tiket_update_result_{sync_id}.csv')
        file_exists = os.path.exists(log_filename)

        with open(log_filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    'Timestamp', 'Nomor Tiket', 'Kategori', 'Detail'
                ])
            writer.writerow([
                timezone.now().isoformat(),
                nomor_tiket or '-',
                kategori,
                detail or '-',
            ])
    except Exception as e:
        logger.error(f"Failed to log update result row: {str(e)}")


def _check_tiket_update_data(service, check_id=None, stop_checker=None):
    """Dry-run check of tiket update data from Oracle without modifying DB.

    Performs actual field-by-field comparison (same logic as _update_tiket_data)
    to accurately count what would change.

    Args:
        service: OracleDataSyncService instance
        check_id: optional UUID for tracking check progress
        stop_checker: optional callable() that returns True if check should stop

    Returns:
        dict with keys: source_rows, would_update, would_identifikasi, would_pmde,
        would_selesai, would_rematch, would_transfer_ulang, would_unchanged,
        errors, updated_keys
    """
    try:
        if check_id:
            cache.set(f'check_tiket_update_progress_{check_id}', {
                'current': 0, 'total': 0, 'percentage': 0,
                'would_update': 0, 'would_identifikasi': 0,
                'would_pmde': 0, 'would_selesai': 0, 'would_rematch': 0,
                'would_transfer_ulang': 0,
                'errors': 0,
                'table_name': 'Menghubungkan ke Oracle...',
            }, timeout=3600)

        with service._connect_oracle("primary") as conn:
            with conn.cursor() as cursor:
                cursor.execute(_TIKET_UPDATE_ORACLE_SQL)
                rows = cursor.fetchall()
                column_names = [desc[0].lower() for desc in cursor.description]

        total = len(rows)
        logger.info(f'Oracle check query completed, fetched {total} rows')

        # Bulk-fetch existing Tikets with full field data for comparison
        all_nomor_tikets = list(dict.fromkeys(
            dict(zip(column_names, r)).get('nomor_tiket') for r in rows
        ))
        existing_tikets_map = {}
        CHUNK = 500
        for i in range(0, len(all_nomor_tikets), CHUNK):
            batch = all_nomor_tikets[i:i + CHUNK]
            for tiket in Tiket.objects.filter(nomor_tiket__in=batch):
                existing_tikets_map[tiket.nomor_tiket] = tiket

        would_update = 0
        would_identifikasi = 0
        would_pmde = 0
        would_selesai = 0
        would_dikembalikan = 0
        would_rematch = 0
        would_transfer_ulang = 0
        would_unchanged = 0
        not_found = 0
        errors = []
        updated_keys = []

        for idx, row in enumerate(rows):
            if stop_checker and stop_checker():
                logger.warning(f'Stop signal received during check after {idx} rows')
                break

            try:
                row_dict = dict(zip(column_names, row))
                nomor_tiket = row_dict.get('nomor_tiket')
                if not nomor_tiket:
                    continue

                tiket = existing_tikets_map.get(nomor_tiket)
                if not tiket:
                    not_found += 1
                    if check_id:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Belum Disinkronisasi',
                            'Nomor tiket tidak ditemukan di database lokal (dry-run)'
                        )
                    continue

                # Compare each field just like _update_tiket_data does
                tgl_transfer = _make_aware_datetime(row_dict.get('tgl_transfer'))
                tgl_rematch = _make_aware_datetime(row_dict.get('tgl_rematch'))
                tgl_rekam_pide = _make_aware_datetime(row_dict.get('tgl_rekam_pide'))
                baris_i = row_dict.get('baris_i')
                baris_u = row_dict.get('baris_u')
                baris_res = row_dict.get('baris_res')
                baris_cde = row_dict.get('baris_cde')
                sudah_qc = row_dict.get('sudah_qc')
                belum_qc = row_dict.get('belum_qc')
                lolos_qc = row_dict.get('lolos_qc')
                tidak_lolos_qc = row_dict.get('tidak_lolos_qc')
                qc_p = row_dict.get('qc_p')
                qc_x = row_dict.get('qc_x')
                qc_w = row_dict.get('qc_w')
                qc_f = row_dict.get('qc_f')
                qc_a = row_dict.get('qc_a')
                qc_c = row_dict.get('qc_c')
                qc_n = row_dict.get('qc_n')
                qc_y = row_dict.get('qc_y')
                qc_z = row_dict.get('qc_z')
                qc_u = row_dict.get('qc_u')
                qc_e = row_dict.get('qc_e')
                qc_v = row_dict.get('qc_v')
                qc_r = row_dict.get('qc_r')
                qc_d = row_dict.get('qc_d')

                changed = False

                if tgl_transfer != tiket.tgl_transfer:
                    changed = True
                if tgl_rematch != tiket.tgl_rematch:
                    changed = True
                if baris_i is not None and tiket.baris_i != baris_i:
                    changed = True
                if baris_u is not None and tiket.baris_u != baris_u:
                    changed = True
                if baris_res is not None and tiket.baris_res != baris_res:
                    changed = True
                if baris_cde is not None and tiket.baris_cde != baris_cde:
                    changed = True
                if sudah_qc is not None and tiket.sudah_qc != sudah_qc:
                    changed = True
                if belum_qc is not None and tiket.belum_qc != belum_qc:
                    changed = True
                if lolos_qc is not None and tiket.lolos_qc != lolos_qc:
                    changed = True
                if tidak_lolos_qc is not None and tiket.tidak_lolos_qc != tidak_lolos_qc:
                    changed = True
                if qc_p is not None and tiket.qc_p != qc_p:
                    changed = True
                if qc_x is not None and tiket.qc_x != qc_x:
                    changed = True
                if qc_w is not None and tiket.qc_w != qc_w:
                    changed = True
                if qc_f is not None and tiket.qc_f != qc_f:
                    changed = True
                if qc_a is not None and tiket.qc_a != qc_a:
                    changed = True
                if qc_c is not None and tiket.qc_c != qc_c:
                    changed = True
                if qc_n is not None and tiket.qc_n != qc_n:
                    changed = True
                if qc_y is not None and tiket.qc_y != qc_y:
                    changed = True
                if qc_z is not None and tiket.qc_z != qc_z:
                    changed = True
                if qc_u is not None and tiket.qc_u != qc_u:
                    changed = True
                if qc_e is not None and tiket.qc_e != qc_e:
                    changed = True
                if qc_v is not None and tiket.qc_v != qc_v:
                    changed = True
                if qc_r is not None and tiket.qc_r != qc_r:
                    changed = True
                if qc_d is not None and tiket.qc_d != qc_d:
                    changed = True

                # Status transitions — only count if tiket status matches
                pending_rekam_pide = (
                    tiket.status_tiket == STATUS_DIKIRIM_KE_PIDE
                    and tiket.tgl_rekam_pide is None
                    and tgl_rekam_pide is not None
                )
                needs_identifikasi = pending_rekam_pide and tgl_transfer is None
                needs_pmde_from_4 = pending_rekam_pide and tgl_transfer is not None
                needs_pmde = (
                    tiket.status_tiket == STATUS_IDENTIFIKASI
                    and tgl_transfer is not None
                    and baris_i is not None
                    and baris_i > 0
                    and (belum_qc is None or belum_qc != 0)
                )
                hanya_cde = _hanya_cde(baris_i, baris_u, baris_res, baris_cde)
                qc_lengkap = _qc_lengkap(baris_i, baris_u, baris_res, baris_cde, sudah_qc, belum_qc)
                needs_selesai = (
                    tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
                    and qc_lengkap
                )
                needs_selesai_from_5 = (
                    tiket.status_tiket == STATUS_IDENTIFIKASI
                    and tgl_transfer is not None
                    and qc_lengkap
                )

                needs_dikembalikan = (
                    tiket.status_tiket == STATUS_IDENTIFIKASI
                    and tgl_transfer is not None
                    and hanya_cde
                )

                needs_selesai_from_5_baris = (
                    tiket.status_tiket == STATUS_IDENTIFIKASI
                    and tgl_transfer is not None
                    and (belum_qc is None or belum_qc != 0)
                    and (
                        (baris_i is not None and baris_i == 0
                         and baris_u is not None and baris_u > 0)
                        or
                        (baris_i is not None and baris_i == 0
                         and baris_u is not None and baris_u == 0
                         and baris_res is not None and baris_res > 0
                         and baris_cde is not None and baris_cde == 0)
                    )
                )

                # Rematch di Oracle memunculkan baris QC baru pada tiket yang
                # sudah ditutup, jadi tiket dibuka kembali ke pengendalian mutu.
                needs_rematch = (
                    tiket.status_tiket == STATUS_SELESAI
                    and tgl_rematch is not None
                    and belum_qc is not None
                    and belum_qc > 0
                )

                # PIC PIDE merevisi tarikan: transfer ulang dengan tanggal baru,
                # dan kali ini baris identifikasi ikut terisi. Tiket yang sudah
                # ditutup lewat Aturan 5 (baris_u saja) kini punya baris_i > 0,
                # jadi harus melewati pengendalian mutu dulu. Syaratnya sengaja
                # dibuat sama persis dengan Aturan 1 — komposisi baris yang sama
                # harus mendarat di status yang sama, dari 5 maupun dari 8.
                needs_transfer_ulang = (
                    tiket.status_tiket == STATUS_SELESAI
                    and tgl_rematch is None
                    and tgl_transfer is not None
                    and tgl_transfer != tiket.tgl_transfer
                    and baris_i is not None
                    and baris_i > 0
                    and (belum_qc is None or belum_qc != 0)
                )

                if needs_identifikasi:
                    changed = True
                if needs_pmde_from_4:
                    changed = True
                if needs_pmde:
                    changed = True
                if needs_selesai:
                    changed = True
                if needs_selesai_from_5:
                    changed = True
                if needs_dikembalikan:
                    changed = True
                if needs_selesai_from_5_baris:
                    changed = True
                if needs_rematch:
                    changed = True
                if needs_transfer_ulang:
                    changed = True

                if not changed:
                    would_unchanged += 1
                    if check_id:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Tidak Berubah',
                            'Data sudah sinkron, tidak ada perubahan (dry-run)'
                        )
                    continue

                would_update += 1
                if needs_identifikasi:
                    would_identifikasi += 1
                if needs_pmde_from_4:
                    would_pmde += 1
                if needs_pmde:
                    would_pmde += 1
                if needs_selesai:
                    would_selesai += 1
                if needs_selesai_from_5:
                    would_selesai += 1
                if needs_dikembalikan:
                    would_dikembalikan += 1
                if needs_selesai_from_5_baris:
                    would_selesai += 1
                if needs_rematch:
                    would_rematch += 1
                if needs_transfer_ulang:
                    would_transfer_ulang += 1
                if len(updated_keys) < 5:
                    updated_keys.append(nomor_tiket)

                if check_id:
                    # Determine which fields would change
                    detail_parts = []
                    if needs_identifikasi:
                        detail_parts.append(f"Status: DIKIRIM_KE_PIDE → IDENTIFIKASI (Tgl Rekam PIDE:{tgl_rekam_pide})")
                    if needs_pmde_from_4:
                        detail_parts.append(f"Status: DIKIRIM_KE_PIDE → PENGENDALIAN_MUTU (Tgl Rekam PIDE:{tgl_rekam_pide}, Tgl Transfer:{tgl_transfer})")
                    if needs_pmde:
                        detail_parts.append(f"Status: IDENTIFIKASI → PENGENDALIAN_MUTU (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})")
                    if needs_selesai:
                        detail_parts.append(f"Status: PENGENDALIAN_MUTU → SELESAI (Sudah QC:{sudah_qc}, Lolos QC:{lolos_qc}, Tidak Lolos QC:{tidak_lolos_qc})")
                    if needs_selesai_from_5:
                        detail_parts.append(f"Status: IDENTIFIKASI → SELESAI (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde}, Sudah QC:{sudah_qc}, Lolos QC:{lolos_qc}, Tidak Lolos QC:{tidak_lolos_qc})")
                    if needs_dikembalikan:
                        detail_parts.append(f"Status: IDENTIFIKASI → DIBATALKAN (dikembalikan PIDE, I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})")
                    if needs_selesai_from_5_baris:
                        detail_parts.append(f"Status: IDENTIFIKASI → SELESAI (langsung, I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})")
                    if needs_rematch:
                        detail_parts.append(f"Status: SELESAI → PENGENDALIAN_MUTU (rematch, Tgl Rematch:{tgl_rematch}, Belum QC:{belum_qc})")
                    if needs_transfer_ulang:
                        detail_parts.append(f"Status: SELESAI → PENGENDALIAN_MUTU (transfer ulang, Tgl Transfer:{tiket.tgl_transfer} → {tgl_transfer}, I:{baris_i}, U:{baris_u})")
                    if not detail_parts:
                        detail_parts.append('Data kolom akan diperbarui')

                    _log_update_result_row(
                        check_id, nomor_tiket,
                        'Akan Diupdate',
                        ' | '.join(detail_parts) if detail_parts else 'Data akan diperbarui (dry-run)'
                    )
                    if needs_identifikasi:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Akan → Identifikasi',
                            f'Dari DIKIRIM_KE_PIDE ke IDENTIFIKASI (Tgl Rekam PIDE:{tgl_rekam_pide})'
                        )
                    if needs_pmde_from_4:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Akan → Pengendalian Mutu',
                            f'Dari DIKIRIM_KE_PIDE ke PENGENDALIAN_MUTU (Tgl Rekam PIDE:{tgl_rekam_pide}, Tgl Transfer:{tgl_transfer})'
                        )
                    if needs_pmde:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Akan → Pengendalian Mutu',
                            f'Dari IDENTIFIKASI ke PENGENDALIAN_MUTU (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})'
                        )
                    if needs_selesai:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Akan → Selesai',
                            f'Dari PENGENDALIAN_MUTU ke SELESAI (Sudah QC:{sudah_qc}, Lolos QC:{lolos_qc}, Tidak Lolos QC:{tidak_lolos_qc})'
                        )
                    if needs_selesai_from_5:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Akan → Selesai (langsung dari Identifikasi)',
                            f'Dari IDENTIFIKASI langsung ke SELESAI (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde}, Sudah QC:{sudah_qc})'
                        )
                    if needs_dikembalikan:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Akan → Dikembalikan',
                            f'Dari IDENTIFIKASI ke DIBATALKAN (dikembalikan PIDE, I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})'
                        )
                    if needs_selesai_from_5_baris:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Akan → Selesai (langsung dari Identifikasi - baris)',
                            f'Dari IDENTIFIKASI langsung ke SELESAI (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})'
                        )
                    if needs_rematch:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Akan → Pengendalian Mutu (rematch)',
                            f'Dari SELESAI ke PENGENDALIAN_MUTU (Tgl Rematch:{tgl_rematch}, Belum QC:{belum_qc})'
                        )
                    if needs_transfer_ulang:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Akan → Pengendalian Mutu (transfer ulang)',
                            f'Dari SELESAI ke PENGENDALIAN_MUTU (Tgl Transfer:{tiket.tgl_transfer} → {tgl_transfer}, I:{baris_i}, U:{baris_u}, Belum QC:{belum_qc})'
                        )

            except Exception as e:
                try:
                    row_id = row_dict.get('nomor_tiket', f'row_{idx + 1}')
                except (NameError, AttributeError):
                    row_id = f'row_{idx + 1}'
                errors.append(f'Row {row_id}: {str(e)[:100]}')
                if check_id:
                    _log_update_result_row(
                        check_id, row_id,
                        'Error',
                        str(e)[:200]
                    )

            if check_id and (idx % 1000 == 0 or idx == total - 1):
                pct = int((idx + 1) / total * 100) if total else 100
                cache.set(f'check_tiket_update_progress_{check_id}', {
                    'current': idx + 1, 'total': total, 'percentage': pct,
                    'would_update': would_update,
                    'would_identifikasi': would_identifikasi,
                    'would_pmde': would_pmde,
                    'would_selesai': would_selesai,
                    'would_dikembalikan': would_dikembalikan,
                    'would_rematch': would_rematch,
                    'would_transfer_ulang': would_transfer_ulang,
                    'would_unchanged': would_unchanged,
                    'not_found': not_found,
                    'errors': len(errors),
                    'table_name': 'Memeriksa baris...',
                }, timeout=3600)

        logger.info(
            f'Check complete: {total} oracle rows, {would_update} would update, '
            f'{would_unchanged} unchanged, {not_found} not found in DB, '
            f'{would_identifikasi} → Identifikasi, '
            f'{would_pmde} → PMDE, {would_selesai} → Selesai, '
            f'{would_dikembalikan} → Dikembalikan, {would_rematch} → PMDE (rematch), '
            f'{would_transfer_ulang} → PMDE (transfer ulang)'
        )
        return {
            'source_rows': total,
            'would_update': would_update,
            'would_identifikasi': would_identifikasi,
            'would_pmde': would_pmde,
            'would_selesai': would_selesai,
            'would_dikembalikan': would_dikembalikan,
            'would_rematch': would_rematch,
            'would_transfer_ulang': would_transfer_ulang,
            'would_unchanged': would_unchanged,
            'not_found': not_found,
            'errors': errors,
            'updated_keys': updated_keys,
        }
    except Exception as e:
        logger.error(f'Check failed: {str(e)}', exc_info=True)
        return {
            'source_rows': 0, 'would_update': 0, 'would_identifikasi': 0,
            'would_pmde': 0, 'would_selesai': 0,
            'would_dikembalikan': 0, 'would_rematch': 0,
            'would_transfer_ulang': 0,
            'would_unchanged': 0, 'not_found': 0,
            'errors': [str(e)], 'updated_keys': [],
        }


def _plan_tiket_update(tiket, row_dict, koreksi=False):
    """Work out what the sync does to *tiket* for one Oracle row, writing nothing.

    This is the rule book of the tiket update sync: the field comparison and
    every status transition (Aturan 1-9 in docs/SYNC_TIKET_UPDATE_RULES.md).
    The bulk sync applies the plan straight away; the tiket detail page shows
    it as a preview first, so both run exactly the same rules.

    Every rule reads the tiket as it stands before this row: the field update
    never feeds a transition, and the transitions do not chain within a run.

    With *koreksi* (the tiket detail page only), a cancel or close by the
    sync that the rekap no longer bears out is undone first
    (`_plan_koreksi`), and the rules read the tiket as the
    correction leaves it.

    Returns:
        dict with keys:
            values: the row's values, dates made DB-safe
            status_from: the tiket status before the sync
            koreksi: the correction from `_plan_koreksi`, or None
            field_changes: [(field, old, new)] from the general field update
            transitions: transition dicts in the order the sync applies them;
                each has key, aturan, counter, status_to, fields (extra
                fields it writes), actions [(role, action, timestamp,
                catatan)], notify_p3de (message or None), log_kategori and
                log_detail
            changed: whether the sync would write anything
    """
    values = dict(row_dict)
    for field in ('tgl_transfer', 'tgl_rematch', 'tgl_close_tiket', 'tgl_rekam_pide'):
        values[field] = _make_aware_datetime(row_dict.get(field))

    status_from = tiket.status_tiket
    koreksi_plan = _plan_koreksi(tiket, values) if koreksi else None
    if koreksi_plan:
        tiket = copy.copy(tiket)
        for field, value in koreksi_plan['fields'].items():
            setattr(tiket, field, value)

    tgl_transfer = values['tgl_transfer']
    tgl_rematch = values['tgl_rematch']
    tgl_close_tiket = values['tgl_close_tiket']
    tgl_rekam_pide = values['tgl_rekam_pide']
    baris_i = values.get('baris_i')
    baris_u = values.get('baris_u')
    baris_res = values.get('baris_res')
    baris_cde = values.get('baris_cde')
    sudah_qc = values.get('sudah_qc')
    belum_qc = values.get('belum_qc')
    lolos_qc = values.get('lolos_qc')
    tidak_lolos_qc = values.get('tidak_lolos_qc')

    field_changes = []
    for field in _SYNC_DATE_FIELDS:
        old = getattr(tiket, field)
        if values[field] != old:
            field_changes.append((field, old, values[field]))
    for field in _SYNC_COUNT_FIELDS:
        new = values.get(field)
        old = getattr(tiket, field)
        if new is not None and old != new:
            field_changes.append((field, old, new))

    # Tiket masih di PIDE tanpa tgl_rekam_pide lokal: Oracle sudah
    # merekam tgl_load, jadi identifikasi (dan transfer) di-backfill.
    pending_rekam_pide = (
        tiket.status_tiket == STATUS_DIKIRIM_KE_PIDE
        and tiket.tgl_rekam_pide is None
        and tgl_rekam_pide is not None
    )
    needs_identifikasi = pending_rekam_pide and tgl_transfer is None
    needs_pmde_from_4 = pending_rekam_pide and tgl_transfer is not None
    needs_pmde = (
        tiket.status_tiket == STATUS_IDENTIFIKASI
        and tgl_transfer is not None
        and baris_i is not None
        and baris_i > 0
        and (belum_qc is None or belum_qc != 0)
    )
    hanya_cde = _hanya_cde(baris_i, baris_u, baris_res, baris_cde)
    qc_lengkap = _qc_lengkap(baris_i, baris_u, baris_res, baris_cde, sudah_qc, belum_qc)
    needs_selesai = (
        tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
        and qc_lengkap
    )
    needs_selesai_from_5 = (
        tiket.status_tiket == STATUS_IDENTIFIKASI
        and tgl_transfer is not None
        and qc_lengkap
    )
    needs_dikembalikan = (
        tiket.status_tiket == STATUS_IDENTIFIKASI
        and tgl_transfer is not None
        and hanya_cde
    )
    needs_selesai_from_5_baris = (
        tiket.status_tiket == STATUS_IDENTIFIKASI
        and tgl_transfer is not None
        and (belum_qc is None or belum_qc != 0)
        and (
            (baris_i is not None and baris_i == 0
             and baris_u is not None and baris_u > 0)
            or
            (baris_i is not None and baris_i == 0
             and baris_u is not None and baris_u == 0
             and baris_res is not None and baris_res > 0
             and baris_cde is not None and baris_cde == 0)
        )
    )
    # Rematch di Oracle memunculkan baris QC baru pada tiket yang
    # sudah ditutup, jadi tiket dibuka kembali ke pengendalian mutu.
    needs_rematch = (
        tiket.status_tiket == STATUS_SELESAI
        and tgl_rematch is not None
        and belum_qc is not None
        and belum_qc > 0
    )
    # PIC PIDE merevisi tarikan: transfer ulang dengan tanggal baru,
    # dan kali ini baris identifikasi ikut terisi. Tiket yang sudah
    # ditutup lewat Aturan 5 (baris_u saja) kini punya baris_i > 0,
    # jadi harus melewati pengendalian mutu dulu. Syaratnya sengaja
    # dibuat sama persis dengan Aturan 1 — komposisi baris yang sama
    # harus mendarat di status yang sama, dari 5 maupun dari 8.
    needs_transfer_ulang = (
        tiket.status_tiket == STATUS_SELESAI
        and tgl_rematch is None
        and tgl_transfer is not None
        and tgl_transfer != tiket.tgl_transfer
        and baris_i is not None
        and baris_i > 0
        and (belum_qc is None or belum_qc != 0)
    )

    now = timezone.now()
    PIDE, PMDE, P3DE = TiketPIC.Role.PIDE, TiketPIC.Role.PMDE, TiketPIC.Role.P3DE
    baris = f'I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde}'

    def transition(key, aturan, counter, status_to, actions, log_kategori,
                   log_detail, fields=None, notify_p3de=None):
        return {
            'key': key, 'aturan': aturan, 'counter': counter,
            'status_to': status_to, 'fields': fields or {},
            'actions': actions, 'notify_p3de': notify_p3de,
            'log_kategori': log_kategori, 'log_detail': log_detail,
        }

    # Aturan 3 & 5 write the same trail: PIDE transfers, PMDE closes QC.
    selesai_from_5_actions = [
        (PIDE, TiketActionType.DITRANSFER_KE_PMDE, tgl_transfer or now, CATATAN_DITRANSFER),
        (PMDE, TiketActionType.PENGENDALIAN_MUTU, tgl_transfer or now, CATATAN_PENGENDALIAN_MUTU),
        (PMDE, TiketActionType.SELESAI, tgl_close_tiket or now, CATATAN_SELESAI),
    ]

    transitions = []
    if needs_identifikasi:
        transitions.append(transition(
            'identifikasi', 6, 'status_to_identifikasi', STATUS_IDENTIFIKASI,
            fields={'tgl_rekam_pide': tgl_rekam_pide},
            actions=[(PIDE, TiketActionType.IDENTIFIKASI, tgl_rekam_pide or now, 'Mulai proses identifikasi')],
            log_kategori='Status → Identifikasi',
            log_detail=f'Dari DIKIRIM_KE_PIDE ke IDENTIFIKASI (Tgl Rekam PIDE:{tgl_rekam_pide})',
        ))
    if needs_pmde_from_4:
        transitions.append(transition(
            'pmde_from_4', 7, 'status_to_pmde', STATUS_PENGENDALIAN_MUTU,
            fields={'tgl_rekam_pide': tgl_rekam_pide, 'tgl_transfer': tgl_transfer},
            actions=[
                (PIDE, TiketActionType.IDENTIFIKASI, tgl_rekam_pide or now, 'Mulai proses identifikasi'),
                (PIDE, TiketActionType.DITRANSFER_KE_PMDE, tgl_transfer or now, CATATAN_DITRANSFER),
            ],
            log_kategori='Status → Pengendalian Mutu',
            log_detail=f'Dari DIKIRIM_KE_PIDE ke PENGENDALIAN_MUTU (Tgl Rekam PIDE:{tgl_rekam_pide}, Tgl Transfer:{tgl_transfer})',
        ))
    if needs_pmde:
        transitions.append(transition(
            'pmde', 1, 'status_to_pmde', STATUS_PENGENDALIAN_MUTU,
            actions=[(PIDE, TiketActionType.DITRANSFER_KE_PMDE, tgl_transfer or now, CATATAN_DITRANSFER)],
            log_kategori='Status → Pengendalian Mutu',
            log_detail=f'Dari IDENTIFIKASI ke PENGENDALIAN_MUTU ({baris})',
        ))
    if needs_selesai:
        transitions.append(transition(
            'selesai', 2, 'status_to_selesai', STATUS_SELESAI,
            actions=[
                (PMDE, TiketActionType.PENGENDALIAN_MUTU, tgl_transfer or now, CATATAN_PENGENDALIAN_MUTU),
                (PMDE, TiketActionType.SELESAI, tgl_close_tiket or now, CATATAN_SELESAI_ATURAN_2),
            ],
            log_kategori='Status → Selesai',
            log_detail=f'Dari PENGENDALIAN_MUTU ke SELESAI (Sudah QC:{sudah_qc}, Lolos QC:{lolos_qc}, Tidak Lolos QC:{tidak_lolos_qc})',
        ))
    if needs_selesai_from_5:
        transitions.append(transition(
            'selesai_from_5', 3, 'status_to_selesai', STATUS_SELESAI,
            actions=selesai_from_5_actions,
            log_kategori='Status → Selesai (langsung dari Identifikasi)',
            log_detail=f'Dari IDENTIFIKASI langsung ke SELESAI ({baris}, Sudah QC:{sudah_qc})',
        ))
    if needs_dikembalikan:
        # Same as PIDE's manual Dikembalikan: the tiket is cancelled.
        tgl_dikembalikan = dikembalikan_timestamp(tiket, tgl_transfer or now)
        transitions.append(transition(
            'dikembalikan', 4, 'status_to_dikembalikan', STATUS_DIBATALKAN,
            fields={'tgl_dikembalikan': tgl_dikembalikan, 'tgl_rekam_pide': None},
            actions=[
                (PIDE, TiketActionType.DIKEMBALIKAN, tgl_dikembalikan, CATATAN_DIKEMBALIKAN_AUTO_SYNC),
                (P3DE, TiketActionType.DIBATALKAN, tgl_dikembalikan, CATATAN_DIBATALKAN_AUTO_SYNC),
            ],
            notify_p3de=f'Tiket {tiket.nomor_tiket} telah dikembalikan oleh PIDE (auto-sync)',
            log_kategori='Status → Dikembalikan',
            log_detail=f'Dari IDENTIFIKASI ke DIBATALKAN (dikembalikan PIDE, {baris})',
        ))
    if needs_selesai_from_5_baris:
        transitions.append(transition(
            'selesai_from_5_baris', 5, 'status_to_selesai', STATUS_SELESAI,
            actions=selesai_from_5_actions,
            log_kategori='Status → Selesai (langsung dari Identifikasi - baris)',
            log_detail=f'Dari IDENTIFIKASI langsung ke SELESAI ({baris})',
        ))
    if needs_rematch:
        transitions.append(transition(
            'rematch', 8, 'status_to_rematch', STATUS_PENGENDALIAN_MUTU,
            actions=[(PIDE, TiketActionType.REMATCH, tgl_rematch or now, 'Tiket di-rematch oleh PIDE (auto-sync)')],
            log_kategori='Status → Pengendalian Mutu (rematch)',
            log_detail=f'Dari SELESAI ke PENGENDALIAN_MUTU (Tgl Rematch:{tgl_rematch}, Belum QC:{belum_qc})',
        ))
    if needs_transfer_ulang:
        # Aksi transfer yang baru, bukan koreksi yang lama: jejak
        # Ditransfer/Pengendalian Mutu/Selesai sebelumnya tetap
        # utuh sebagai riwayat putaran tarikan yang sudah lewat.
        transitions.append(transition(
            'transfer_ulang', 9, 'status_to_transfer_ulang', STATUS_PENGENDALIAN_MUTU,
            actions=[(
                PIDE, TiketActionType.DITRANSFER_KE_PMDE, tgl_transfer or now,
                f'Tiket ditransfer ulang ke PMDE — revisi tarikan oleh PIDE (I:{baris_i}, U:{baris_u})',
            )],
            log_kategori='Status → Pengendalian Mutu (transfer ulang)',
            log_detail=f'Dari SELESAI ke PENGENDALIAN_MUTU (Tgl Transfer:{tiket.tgl_transfer} → {tgl_transfer}, I:{baris_i}, U:{baris_u}, Belum QC:{belum_qc})',
        ))

    return {
        'values': values,
        'status_from': status_from,
        'koreksi': koreksi_plan,
        'field_changes': field_changes,
        'transitions': transitions,
        'changed': bool(koreksi_plan or field_changes or transitions),
    }


def _apply_tiket_update_plan(tiket, plan, tiket_pics, sync_id):
    """Write a plan from `_plan_tiket_update` to *tiket* and its audit trail.

    Args:
        tiket: the Tiket the plan was made for, unchanged since
        plan: the plan, with ``changed`` True
        tiket_pics: the tiket's active PICs as {role: [TiketPIC, ...]}; each
            action goes to the first PIC of its role and is skipped, with a
            warning, when the role has none
        sync_id: the operation id the result CSV is written under
    """
    nomor_tiket = tiket.nomor_tiket
    update_fields = []
    koreksi = plan.get('koreksi')
    if koreksi:
        for field, value in koreksi['fields'].items():
            setattr(tiket, field, value)
            update_fields.append(field)
    for field, _old, new in plan['field_changes']:
        setattr(tiket, field, new)
        update_fields.append(field)
    for t in plan['transitions']:
        tiket.status_tiket = t['status_to']
        update_fields.append('status_tiket')
        for field, value in t['fields'].items():
            setattr(tiket, field, value)
            update_fields.append(field)

    tiket.save(update_fields=list(set(update_fields)))

    if koreksi:
        TiketAction.objects.filter(id__in=[a.id for a in koreksi['actions']]).delete()
        judul = KOREKSI_JUDUL[koreksi['jenis']]
        if koreksi['notify_p3de']:
            status_to = STATUS_LABELS.get(tiket.status_tiket, '-')
            for pic in tiket_pics.get(TiketPIC.Role.P3DE, []):
                Notification.objects.create(
                    recipient=pic.id_user,
                    title='Pembatalan Tiket Dikoreksi',
                    message=f"{koreksi['notify_p3de']} Status tiket: {status_to}.",
                )
        logger.info(
            f"Tiket {nomor_tiket}: {judul.lower()} auto-sync, "
            f"{len(koreksi['actions'])} aksi dihapus"
        )
        _log_update_result_row(
            sync_id, nomor_tiket, judul,
            f"Dari {STATUS_LABELS.get(plan['status_from'], '-')} ke "
            f"{STATUS_LABELS.get(koreksi['fields']['status_tiket'], '-')} (hapus aksi " + ', '.join(
                f'{get_action_label(a.action)} {a.timestamp:%d/%m/%Y %H:%M}'
                for a in koreksi['actions']
            ) + ')',
        )

    # Log field updates detail
    updated_field_names = list(set(update_fields) - {'status_tiket'})
    detail_parts = []
    if updated_field_names:
        detail_parts.append(f"Field: {', '.join(updated_field_names)}")
    if any(t['key'] == 'pmde' for t in plan['transitions']):
        v = plan['values']
        detail_parts.append(f"I:{v.get('baris_i')}, U:{v.get('baris_u')}, Res:{v.get('baris_res')}, CDE:{v.get('baris_cde')}")

    _log_update_result_row(
        sync_id, nomor_tiket,
        'Baris Diupdate',
        ' | '.join(detail_parts) if detail_parts else 'Data diperbarui'
    )

    for t in plan['transitions']:
        for role, action, timestamp, catatan in t['actions']:
            pics = tiket_pics.get(role, [])
            user = pics[0].id_user if pics else None
            if user:
                TiketAction.objects.create(
                    id_tiket=tiket, id_user=user,
                    timestamp=timestamp, action=action, catatan=catatan,
                )
            else:
                logger.warning(
                    f'Tiket {nomor_tiket}: no active {TiketPIC.Role(role).label} PIC — '
                    f'status updated but {get_action_label(action)} action skipped'
                )

        if t['notify_p3de']:
            for pic in tiket_pics.get(TiketPIC.Role.P3DE, []):
                Notification.objects.create(
                    recipient=pic.id_user,
                    title='Tiket Dikembalikan',
                    message=t['notify_p3de'],
                )

        logger.info(f"Tiket {nomor_tiket}: {plan['status_from']} → {t['status_to']} (auto-sync, Aturan {t['aturan']})")
        _log_update_result_row(sync_id, nomor_tiket, t['log_kategori'], t['log_detail'])


def _active_pics_by_role(pics):
    """Group active TiketPIC rows as {role: [pic, ...]}, keeping their order."""
    by_role = {}
    for pic in pics:
        by_role.setdefault(pic.role, []).append(pic)
    return by_role


class TiketUpdateRowError(Exception):
    """Oracle's rows for a single tiket cannot be synchronised unambiguously."""


def _fetch_tiket_update_row(service, nomor_tiket):
    """Return the sync row Oracle holds for one tiket, or None when it has none.

    Runs the bulk sync's own query, narrowed to the raw no_tiket values that
    map to *nomor_tiket*: the tiket itself and, for an ``EI`` number, the
    16-character ``E`` form the query rewrites to it.

    Raises:
        TiketUpdateRowError: when both raw forms exist in Oracle, so it holds
            two rows for the tiket and neither is authoritative.
    """
    candidates = [nomor_tiket]
    if len(nomor_tiket) == 17 and nomor_tiket.startswith('EI'):
        candidates.append('E' + nomor_tiket[2:])
    binds = {f'no_tiket_{i}': n for i, n in enumerate(candidates)}
    placeholders = ', '.join(f':{name}' for name in binds)
    sql = _TIKET_UPDATE_ORACLE_SQL_TEMPLATE.format(filter=f'WHERE no_tiket IN ({placeholders})')

    with service._connect_oracle("primary") as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, binds)
            rows = cursor.fetchall()
            column_names = [desc[0].lower() for desc in cursor.description]

    matches = [
        row_dict for row_dict in (dict(zip(column_names, row)) for row in rows)
        if row_dict.get('nomor_tiket') == nomor_tiket
    ]
    if len(matches) > 1:
        raise TiketUpdateRowError(
            f'Oracle memiliki {len(matches)} baris rekap untuk tiket {nomor_tiket} '
            f'(no_tiket {" dan ".join(candidates)}), sehingga tidak dapat disinkronkan.'
        )
    return matches[0] if matches else None


def _update_tiket_data(service, sync_id=None, stop_checker=None):
    """Update tiket QC & transfer columns from Oracle, with status transitions.

    Args:
        service: OracleDataSyncService instance
        sync_id: optional UUID for tracking sync progress
        stop_checker: optional callable() that returns True if sync should stop

    Returns:
        dict with keys: updated_rows, status_to_identifikasi, status_to_pmde,
        status_to_selesai, status_to_rematch, status_to_transfer_ulang,
        errors, updated_keys
    """
    try:
        db_vendor = db_connection.vendor
        BATCH_SIZE = 50 if db_vendor == 'sqlite' else (500 if db_vendor == 'postgresql' else 250)
        logger.info(f'Using batch size {BATCH_SIZE} for {db_vendor}')

        logger.info('Connecting to Oracle for tiket update sync...')
        with service._connect_oracle("primary") as conn:
            with conn.cursor() as cursor:
                cursor.execute(_TIKET_UPDATE_ORACLE_SQL)
                rows = cursor.fetchall()
                column_names = [desc[0].lower() for desc in cursor.description]
        logger.info(f'Oracle query completed, fetched {len(rows)} rows')

        if not rows:
            logger.info('No rows returned from Oracle query')
            return {
                'updated_rows': 0, 'status_to_identifikasi': 0,
                'status_to_pmde': 0, 'status_to_selesai': 0,
                'status_to_rematch': 0, 'status_to_transfer_ulang': 0,
                'errors': [], 'updated_keys': [],
            }

        # Bulk-fetch existing Tikets
        all_nomor_tikets = list(dict.fromkeys(
            dict(zip(column_names, r)).get('nomor_tiket') for r in rows
        ))
        existing_tikets_map = {}
        CHUNK = 500
        for i in range(0, len(all_nomor_tikets), CHUNK):
            batch = all_nomor_tikets[i:i + CHUNK]
            for tiket in Tiket.objects.filter(nomor_tiket__in=batch).select_related(
                'id_periode_data__id_sub_jenis_data_ilap'
            ):
                existing_tikets_map[tiket.nomor_tiket] = tiket
        logger.info(f'Found {len(existing_tikets_map)} matching local tiket records')

        # Pre-fetch active PICs — chunked like the tiket fetch above, since a
        # single IN (...) over every tiket id blows SQLite's parameter limit.
        tiket_ids = [t.id for t in existing_tikets_map.values()]
        active_pics_map = {}
        for i in range(0, len(tiket_ids), CHUNK):
            batch = tiket_ids[i:i + CHUNK]
            for pic in TiketPIC.objects.filter(id_tiket__in=batch, active=True).select_related('id_user'):
                tiket_id = pic.id_tiket_id
                if tiket_id not in active_pics_map:
                    active_pics_map[tiket_id] = {}
                if pic.role not in active_pics_map[tiket_id]:
                    active_pics_map[tiket_id][pic.role] = []
                active_pics_map[tiket_id][pic.role].append(pic)
        logger.info(f'Pre-fetched active PICs for {len(active_pics_map)} tiket')

        updated_rows = 0
        counters = dict.fromkeys((
            'status_to_identifikasi', 'status_to_pmde', 'status_to_selesai',
            'status_to_dikembalikan', 'status_to_rematch', 'status_to_transfer_ulang',
        ), 0)
        not_found_count = 0
        unchanged_count = 0
        errors = []
        updated_keys = []

        for idx, row in enumerate(rows):
            if stop_checker and stop_checker():
                logger.warning(f'Stop signal received during tiket update after {idx} rows')
                break

            if idx % 50 == 0 and sync_id:
                pct = int((idx / len(rows)) * 100) if rows else 0
                cache.set(f'tiket_update_progress_{sync_id}', {
                    'current': idx, 'total': len(rows), 'percentage': pct,
                    'updated_rows': updated_rows,
                    **counters,
                    'not_found': not_found_count,
                    'unchanged': unchanged_count,
                    'errors': len(errors),
                }, timeout=3600)

            try:
                row_dict = dict(zip(column_names, row))
                nomor_tiket = row_dict.get('nomor_tiket')
                if not nomor_tiket:
                    continue

                tiket = existing_tikets_map.get(nomor_tiket)
                if not tiket:
                    not_found_count += 1
                    _log_update_result_row(
                        sync_id, nomor_tiket,
                        'Belum Disinkronisasi',
                        'Nomor tiket tidak ditemukan di database lokal'
                    )
                    continue

                plan = _plan_tiket_update(tiket, row_dict)
                if not plan['changed']:
                    unchanged_count += 1
                    _log_update_result_row(
                        sync_id, nomor_tiket,
                        'Tidak Berubah',
                        'Data sudah sinkron, tidak ada perubahan'
                    )
                    continue

                _apply_tiket_update_plan(tiket, plan, active_pics_map.get(tiket.id, {}), sync_id)
                updated_rows += 1
                if len(updated_keys) < 5:
                    updated_keys.append(nomor_tiket)

                for t in plan['transitions']:
                    counters[t['counter']] += 1

            except Exception as e:
                error_msg = str(e)[:200]
                try:
                    row_id = row_dict.get('nomor_tiket', f'row_{idx + 1}')
                except (NameError, AttributeError):
                    row_id = f'row_{idx + 1}'
                errors.append(f'Tiket {row_id}: {error_msg}')
                _log_failed_row(sync_id, row_id, error_msg, row_number=idx + 1)
                _log_update_result_row(
                    sync_id, row_id if row_id else nomor_tiket,
                    'Error',
                    error_msg
                )
                logger.error(f'Failed to update tiket {row_id}: {error_msg}')

        return {
            'source_rows': len(rows),
            'updated_rows': updated_rows,
            **counters,
            'not_found': not_found_count,
            'unchanged': unchanged_count,
            'errors': errors,
            'updated_keys': updated_keys,
        }
    except Exception as e:
        logger.error(f'Tiket update sync failed: {str(e)}', exc_info=True)
        return {
            'source_rows': 0, 'updated_rows': 0, 'status_to_identifikasi': 0,
            'status_to_pmde': 0, 'status_to_selesai': 0,
            'status_to_dikembalikan': 0, 'status_to_rematch': 0,
            'status_to_transfer_ulang': 0,
            'not_found': 0, 'unchanged': 0,
            'errors': [str(e)], 'updated_keys': [],
        }


# ====== View Endpoints ======


@login_required
@user_passes_test(_is_admin_user)
@require_POST
def sync_tiket_update_test_connection(request):
    """Test Oracle database connection."""
    try:
        service = OracleDataSyncService(connection_only=True)
        with service._connect_oracle("primary") as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")

        secondary = service.oracle_connections.get("secondary")
        secondary_configured = bool(
            secondary and secondary.user and secondary.password
            and secondary.host and (secondary.service_name or secondary.sid)
        )
        secondary_message = "Secondary tidak dikonfigurasi."
        if secondary_configured:
            with service._connect_oracle("secondary") as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM DUAL")
            secondary_message = "Koneksi secondary berhasil."

        return JsonResponse({
            'success': True, 'message': 'Koneksi Oracle berhasil.',
            'connections': {
                'primary': 'Koneksi primary berhasil.',
                'secondary': secondary_message,
            }
        })
    except OracleSyncConfigError as exc:
        return JsonResponse({'success': False, 'message': str(exc).strip()}, status=400)
    except Exception as exc:
        error_msg = str(exc).strip()
        if not error_msg or '<' in error_msg:
            error_msg = 'Gagal koneksi ke Oracle server. Periksa konfigurasi dan konektivitas network.'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def sync_tiket_update_check(request):
    """Start a dry-run check of tiket update data via Celery task."""
    try:
        check_id = str(uuid.uuid4())
        cache.set(f'check_tiket_update_done_{check_id}', False, timeout=3600)
        cache.set(f'check_tiket_update_in_progress_{check_id}', True, timeout=3600)

        logger.info(f'Dispatching tiket update check task (check_id={check_id})...')
        task_result = check_tiket_update_data_task.delay(check_id)
        cache.set(f'check_tiket_update_celery_task_id_{check_id}', task_result.id, timeout=3600)

        return JsonResponse({
            'success': True, 'mode': 'check',
            'check_id': check_id,
            'message': 'Check dimulai. Silakan tunggu...',
        })
    except OracleSyncConfigError as exc:
        return JsonResponse({'success': False, 'message': str(exc).strip()}, status=400)
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Exception in check: {error_msg}', exc_info=True)
        if not error_msg or '<' in error_msg:
            error_msg = 'Gagal melakukan check data tiket. Periksa koneksi Oracle.'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def sync_tiket_update_run(request):
    """Start a tiket update sync via Celery task."""
    try:
        sync_id = str(uuid.uuid4())
        cache.set(f'tiket_update_stop_{sync_id}', False, timeout=3600)
        cache.set(f'tiket_update_done_{sync_id}', False, timeout=3600)
        cache.set(f'tiket_update_in_progress_{sync_id}', True, timeout=3600)

        logger.info(f'Starting tiket update sync (sync_id={sync_id})...')
        task_result = sync_tiket_update_data_task.delay(sync_id, request.user.pk)
        cache.set(f'tiket_update_celery_task_id_{sync_id}', task_result.id, timeout=3600)

        return JsonResponse({
            'success': True, 'mode': 'sync',
            'sync_id': sync_id,
            'message': 'Update dimulai. Silakan tunggu...',
        })
    except OracleSyncConfigError as exc:
        return JsonResponse({'success': False, 'message': str(exc).strip()}, status=400)
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Exception in sync: {error_msg}', exc_info=True)
        if not error_msg or '<' in error_msg:
            error_msg = 'Gagal melakukan update tiket. Periksa koneksi Oracle.'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@require_POST
@never_cache
def sync_tiket_update_stop(request):
    """Stop an in-progress tiket update sync operation."""
    try:
        data = json.loads(request.body)
        sync_id = data.get('sync_id')
        if not sync_id:
            return JsonResponse({'success': False, 'message': 'sync_id tidak ditemukan'}, status=400)
        try:
            uuid.UUID(sync_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'invalid sync_id'}, status=400)

        celery_task_id = cache.get(f'tiket_update_celery_task_id_{sync_id}')
        if celery_task_id:
            try:
                from celery import current_app
                current_app.control.revoke(celery_task_id, terminate=True, signal='SIGTERM')
                logger.info(f'Revoked Celery task {celery_task_id} for sync {sync_id}')
            except Exception as revoke_err:
                logger.warning(f'Failed to revoke Celery task {celery_task_id}: {revoke_err}')

        cache.set(f'tiket_update_stop_{sync_id}', True, timeout=3600)
        cache.set(f'tiket_update_error_{sync_id}', 'Update dihentikan oleh pengguna', timeout=3600)
        cache.set(f'tiket_update_done_{sync_id}', True, timeout=3600)

        request.session.modified = False
        return JsonResponse({'success': True, 'message': 'Update dihentikan.'})
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@require_POST
@never_cache
def sync_tiket_update_stop_check(request):
    """Stop an in-progress tiket update check operation."""
    try:
        data = json.loads(request.body)
        check_id = data.get('check_id', '')
        if not check_id:
            return JsonResponse({'success': False, 'message': 'check_id tidak ditemukan'}, status=400)
        try:
            uuid.UUID(check_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'invalid check_id'}, status=400)

        celery_task_id = cache.get(f'check_tiket_update_celery_task_id_{check_id}')
        if celery_task_id:
            try:
                from celery import current_app
                current_app.control.revoke(celery_task_id, terminate=True, signal='SIGTERM')
                logger.info(f'Revoked Celery task {celery_task_id} for check {check_id}')
            except Exception as revoke_err:
                logger.warning(f'Failed to revoke Celery task {celery_task_id}: {revoke_err}')

        cache.set(f'check_tiket_update_stop_requested_{check_id}', True, timeout=3600)
        cache.set(f'check_tiket_update_error_{check_id}', 'Cek Data dihentikan oleh pengguna', timeout=3600)
        cache.set(f'check_tiket_update_done_{check_id}', True, timeout=3600)

        request.session.modified = False
        return JsonResponse({'success': True, 'message': 'Permintaan stop cek data telah dikirim.'})
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal menghentikan cek data'}, status=500)


@require_GET
@never_cache
def sync_tiket_update_progress(request):
    """Get current progress of a tiket update check or sync operation."""
    try:
        mode = request.GET.get('mode', 'sync')
        request.session.modified = False

        if mode == 'check':
            check_id = request.GET.get('check_id')
            if not check_id:
                return JsonResponse({'success': False, 'message': 'check_id required'}, status=400)
            try:
                uuid.UUID(check_id)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'invalid check_id'}, status=400)

            is_done = cache.get(f'check_tiket_update_done_{check_id}')
            is_in_progress = cache.get(f'check_tiket_update_in_progress_{check_id}')
            progress_data = cache.get(f'check_tiket_update_progress_{check_id}') or {
                'current': 0, 'total': 0, 'percentage': 0,
                'would_update': 0, 'would_identifikasi': 0,
                'would_pmde': 0, 'would_selesai': 0, 'would_rematch': 0,
                'would_transfer_ulang': 0,
                'errors': 0,
            }

            if is_done is None and is_in_progress is None:
                return JsonResponse({'success': False, 'done': True, 'progress': progress_data,
                                     'message': 'Session check kadaluarsa atau tidak ditemukan.'})

            if is_done:
                result = cache.get(f'check_tiket_update_result_{check_id}')
                error = cache.get(f'check_tiket_update_error_{check_id}')
                if error:
                    return JsonResponse({'success': False, 'done': True, 'progress': progress_data, 'message': error})
                if result:
                    response_data = {
                        'success': True, 'done': True,
                        'progress': progress_data, 'summary': result,
                        'message': f"Check selesai: {result.get('would_update', 0)} akan diupdate",
                    }
                    result_log_path = os.path.join(SYNC_LOGS_DIR, f'tiket_update_result_{check_id}.csv')
                    if os.path.exists(result_log_path):
                        response_data['result_log_url'] = reverse(
                            'sync_tiket_update_download_result',
                            kwargs={'operation_id': check_id}
                        )
                    return JsonResponse(response_data)
                return JsonResponse({'success': True, 'done': False, 'progress': progress_data})

            return JsonResponse({'success': True, 'done': False, 'progress': progress_data})

        # mode=sync
        sync_id = request.GET.get('sync_id')
        if not sync_id:
            return JsonResponse({'success': False, 'message': 'sync_id required'}, status=400)
        try:
            uuid.UUID(sync_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'invalid sync_id'}, status=400)

        is_done = cache.get(f'tiket_update_done_{sync_id}')
        is_in_progress = cache.get(f'tiket_update_in_progress_{sync_id}')

        if is_done is None and is_in_progress is None:
            return JsonResponse({'success': False, 'done': True,
                                 'progress': {'current': 0, 'total': 0, 'percentage': 0,
                                              'updated_rows': 0, 'status_to_pmde': 0,
                                              'status_to_selesai': 0, 'errors': 0},
                                 'message': 'Session sync kadaluarsa atau tidak ditemukan.'})

        progress_data = cache.get(f'tiket_update_progress_{sync_id}') or {
            'current': 0, 'total': 0, 'percentage': 0,
            'updated_rows': 0, 'status_to_identifikasi': 0,
            'status_to_pmde': 0, 'status_to_selesai': 0,
            'status_to_rematch': 0, 'status_to_transfer_ulang': 0,
            'errors': 0,
        }

        if is_done:
            result = cache.get(f'tiket_update_result_{sync_id}')
            error = cache.get(f'tiket_update_error_{sync_id}')

            if error:
                return JsonResponse({
                    'success': False, 'done': True, 'progress': progress_data, 'message': error,
                })

            if result:
                response_data = {
                    'success': True, 'done': True,
                    'progress': progress_data, 'summary': result,
                    'message': f"Update selesai: {result.get('updated_rows', 0)} diupdate, {result.get('status_to_identifikasi', 0)} → Identifikasi, {result.get('status_to_pmde', 0)} → PMDE, {result.get('status_to_selesai', 0)} → Selesai, {result.get('status_to_rematch', 0)} → PMDE (rematch), {result.get('status_to_transfer_ulang', 0)} → PMDE (transfer ulang)",
                }
                error_log_path = os.path.join(SYNC_LOGS_DIR, f'tiket_update_failed_rows_{sync_id}.csv')
                if os.path.exists(error_log_path):
                    response_data['error_log_url'] = reverse('sync_tiket_update_download_errors', kwargs={'sync_id': sync_id})
                result_log_path = os.path.join(SYNC_LOGS_DIR, f'tiket_update_result_{sync_id}.csv')
                if os.path.exists(result_log_path):
                    response_data['result_log_url'] = reverse(
                        'sync_tiket_update_download_result',
                        kwargs={'operation_id': sync_id}
                    )
                return JsonResponse(response_data)

        return JsonResponse({'success': True, 'done': False, 'progress': progress_data})
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Exception in progress endpoint: {error_msg}', exc_info=True)
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@require_GET
@never_cache
def sync_tiket_update_download_errors(request, sync_id):
    """Download the error log CSV file for a completed tiket update sync."""
    try:
        try:
            uuid.UUID(sync_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Invalid sync_id format'}, status=400)

        error_log_path = os.path.join(SYNC_LOGS_DIR, f'tiket_update_failed_rows_{sync_id}.csv')

        if not os.path.exists(error_log_path):
            return JsonResponse({'success': False, 'message': 'Error log file not found'}, status=404)

        response = FileResponse(open(error_log_path, 'rb'), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="tiket_update_errors_{sync_id}.csv"'
        return response
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Error downloading tiket update log: {error_msg}', exc_info=True)
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal download error log'}, status=500)


@require_GET
@never_cache
def sync_tiket_update_download_result(request, operation_id):
    """Download the detailed result CSV for a completed tiket update check or sync."""
    try:
        try:
            uuid.UUID(operation_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Invalid operation_id format'}, status=400)

        result_log_path = os.path.join(SYNC_LOGS_DIR, f'tiket_update_result_{operation_id}.csv')

        if not os.path.exists(result_log_path):
            return JsonResponse({'success': False, 'message': 'Result log file not found'}, status=404)

        response = FileResponse(open(result_log_path, 'rb'), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="tiket_update_result_{operation_id}.csv"'
        return response
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Error downloading tiket update result log: {error_msg}', exc_info=True)
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal download result log'}, status=500)
