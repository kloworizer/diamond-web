"""Tiket update sync from Oracle — updates QC columns & status transitions.

This module provides the core logic to:
1. Query Oracle for updated QC/transfer columns (baris_i, baris_u, baris_res,
   baris_cde, tgl_transfer, tgl_rematch, sudah_qc, belum_qc, lolos_qc,
   tidak_lolos_qc, and all qc_* columns).
2. Update matching local Tiket records.
3. Apply status transitions with proper TiketAction audit trail:
   - IDENTIFIKASI (5) + tgl_transfer not null + baris_i > 0
     → PENGENDALIAN_MUTU (6)
   - PENGENDALIAN_MUTU (6) + belum_qc == 0 → SELESAI (8)
   - IDENTIFIKASI (5) + tgl_transfer not null + belum_qc == 0
     → SELESAI (8) (direct, QC complete)
   - IDENTIFIKASI (5) + tgl_transfer not null + i=0 & u=0 & res=0 & cde>0
     → DIKEMBALIKAN (3) (with notification to P3DE)
   - IDENTIFIKASI (5) + tgl_transfer not null + belum_qc != 0
     + (i=0 & u>0) OR (i=0 & u=0 & res>0 & cde=0)
     → SELESAI (8) (direct, baris-based)

See docs/SYNC_TIKET_UPDATE_RULES.md for full documentation.
"""

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
from django.conf import settings
from django.urls import reverse

from ..models.tiket import Tiket
from ..models.tiket_action import TiketAction
from ..models.tiket_pic import TiketPIC
from ..constants.tiket_action_types import TiketActionType
from ..constants.tiket_status import (
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
    STATUS_DIKEMBALIKAN,
)
from ..models.notification import Notification
from ..utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError
from ..tasks import check_tiket_update_data_task, sync_tiket_update_data_task

logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
SYNC_LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sync_logs'
)
os.makedirs(SYNC_LOGS_DIR, exist_ok=True)

# Oracle query to fetch tiket update data (QC columns and transfer dates)
_TIKET_UPDATE_ORACLE_SQL = """
    SELECT
        DISTINCT
        CASE 
            WHEN LENGTH(no_tiket) = 16 AND SUBSTR(no_tiket,1,1) = 'E' THEN SUBSTR(no_tiket, 1, 1) || 'I' || SUBSTR(no_tiket, 2)
            ELSE no_tiket 
        END nomor_tiket,
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
        GROUP BY
            no_tiket
    ) b
"""


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
        dict with keys: source_rows, would_update, would_pmde, would_selesai,
        would_unchanged, errors, updated_keys
    """
    try:
        if check_id:
            cache.set(f'check_tiket_update_progress_{check_id}', {
                'current': 0, 'total': 0, 'percentage': 0,
                'would_update': 0, 'would_pmde': 0, 'would_selesai': 0, 'errors': 0,
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
        would_pmde = 0
        would_selesai = 0
        would_dikembalikan = 0
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
                needs_pmde = (
                    tiket.status_tiket == STATUS_IDENTIFIKASI
                    and tgl_transfer is not None
                    and baris_i is not None
                    and baris_i > 0
                    and (belum_qc is None or belum_qc != 0)
                )
                needs_selesai = (
                    tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
                    and belum_qc is not None
                    and belum_qc == 0
                )
                needs_selesai_from_5 = (
                    tiket.status_tiket == STATUS_IDENTIFIKASI
                    and tgl_transfer is not None
                    and belum_qc is not None
                    and belum_qc == 0
                )

                needs_dikembalikan = (
                    tiket.status_tiket == STATUS_IDENTIFIKASI
                    and tgl_transfer is not None
                    and baris_i is not None and baris_i == 0
                    and baris_u is not None and baris_u == 0
                    and baris_res is not None and baris_res == 0
                    and baris_cde is not None and baris_cde > 0
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
                if len(updated_keys) < 5:
                    updated_keys.append(nomor_tiket)

                if check_id:
                    # Determine which fields would change
                    detail_parts = []
                    if needs_pmde:
                        detail_parts.append(f"Status: IDENTIFIKASI → PENGENDALIAN_MUTU (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})")
                    if needs_selesai:
                        detail_parts.append(f"Status: PENGENDALIAN_MUTU → SELESAI (Sudah QC:{sudah_qc}, Lolos QC:{lolos_qc}, Tidak Lolos QC:{tidak_lolos_qc})")
                    if needs_selesai_from_5:
                        detail_parts.append(f"Status: IDENTIFIKASI → SELESAI (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde}, Sudah QC:{sudah_qc}, Lolos QC:{lolos_qc}, Tidak Lolos QC:{tidak_lolos_qc})")
                    if needs_dikembalikan:
                        detail_parts.append(f"Status: IDENTIFIKASI → DIKEMBALIKAN (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})")
                    if needs_selesai_from_5_baris:
                        detail_parts.append(f"Status: IDENTIFIKASI → SELESAI (langsung, I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})")
                    if not needs_pmde and not needs_selesai and not needs_selesai_from_5 and not needs_dikembalikan and not needs_selesai_from_5_baris:
                        detail_parts.append('Data kolom akan diperbarui')

                    _log_update_result_row(
                        check_id, nomor_tiket,
                        'Akan Diupdate',
                        ' | '.join(detail_parts) if detail_parts else 'Data akan diperbarui (dry-run)'
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
                            f'Dari IDENTIFIKASI ke DIKEMBALIKAN (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})'
                        )
                    if needs_selesai_from_5_baris:
                        _log_update_result_row(
                            check_id, nomor_tiket,
                            'Akan → Selesai (langsung dari Identifikasi - baris)',
                            f'Dari IDENTIFIKASI langsung ke SELESAI (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})'
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
                    'would_pmde': would_pmde,
                    'would_selesai': would_selesai,
                    'would_dikembalikan': would_dikembalikan,
                    'would_unchanged': would_unchanged,
                    'not_found': not_found,
                    'errors': len(errors),
                    'table_name': 'Memeriksa baris...',
                }, timeout=3600)

        logger.info(
            f'Check complete: {total} oracle rows, {would_update} would update, '
            f'{would_unchanged} unchanged, {not_found} not found in DB, '
            f'{would_pmde} → PMDE, {would_selesai} → Selesai, '
            f'{would_dikembalikan} → Dikembalikan'
        )
        return {
            'source_rows': total,
            'would_update': would_update,
            'would_pmde': would_pmde,
            'would_selesai': would_selesai,
            'would_dikembalikan': would_dikembalikan,
            'would_unchanged': would_unchanged,
            'not_found': not_found,
            'errors': errors,
            'updated_keys': updated_keys,
        }
    except Exception as e:
        logger.error(f'Check failed: {str(e)}', exc_info=True)
        return {
            'source_rows': 0, 'would_update': 0,
            'would_pmde': 0, 'would_selesai': 0,
            'would_dikembalikan': 0, 'would_unchanged': 0, 'not_found': 0,
            'errors': [str(e)], 'updated_keys': [],
        }


def _update_tiket_data(service, sync_id=None, stop_checker=None):
    """Update tiket QC & transfer columns from Oracle, with status transitions.

    Args:
        service: OracleDataSyncService instance
        sync_id: optional UUID for tracking sync progress
        stop_checker: optional callable() that returns True if sync should stop

    Returns:
        dict with keys: updated_rows, status_to_pmde, status_to_selesai,
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
                'updated_rows': 0, 'status_to_pmde': 0, 'status_to_selesai': 0,
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

        # Pre-fetch active PICs
        tiket_ids = [t.id for t in existing_tikets_map.values()]
        active_pics_map = {}
        if tiket_ids:
            for pic in TiketPIC.objects.filter(id_tiket__in=tiket_ids, active=True).select_related('id_user'):
                tiket_id = pic.id_tiket_id
                if tiket_id not in active_pics_map:
                    active_pics_map[tiket_id] = {}
                if pic.role not in active_pics_map[tiket_id]:
                    active_pics_map[tiket_id][pic.role] = []
                active_pics_map[tiket_id][pic.role].append(pic)

        updated_rows = 0
        status_to_pmde = 0
        status_to_selesai = 0
        status_to_dikembalikan = 0
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
                    'status_to_pmde': status_to_pmde,
                    'status_to_selesai': status_to_selesai,
                    'status_to_dikembalikan': status_to_dikembalikan,
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

                update_fields = []

                tgl_transfer = _make_aware_datetime(row_dict.get('tgl_transfer'))
                tgl_rematch = _make_aware_datetime(row_dict.get('tgl_rematch'))
                tgl_close_tiket = _make_aware_datetime(row_dict.get('tgl_close_tiket'))

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
                    tiket.tgl_transfer = tgl_transfer
                    update_fields.append('tgl_transfer')
                    changed = True
                if tgl_rematch != tiket.tgl_rematch:
                    tiket.tgl_rematch = tgl_rematch
                    update_fields.append('tgl_rematch')
                    changed = True
                if baris_i is not None and tiket.baris_i != baris_i:
                    tiket.baris_i = baris_i
                    update_fields.append('baris_i')
                    changed = True
                if baris_u is not None and tiket.baris_u != baris_u:
                    tiket.baris_u = baris_u
                    update_fields.append('baris_u')
                    changed = True
                if baris_res is not None and tiket.baris_res != baris_res:
                    tiket.baris_res = baris_res
                    update_fields.append('baris_res')
                    changed = True
                if baris_cde is not None and tiket.baris_cde != baris_cde:
                    tiket.baris_cde = baris_cde
                    update_fields.append('baris_cde')
                    changed = True
                if sudah_qc is not None and tiket.sudah_qc != sudah_qc:
                    tiket.sudah_qc = sudah_qc
                    update_fields.append('sudah_qc')
                    changed = True
                if belum_qc is not None and tiket.belum_qc != belum_qc:
                    tiket.belum_qc = belum_qc
                    update_fields.append('belum_qc')
                    changed = True
                if lolos_qc is not None and tiket.lolos_qc != lolos_qc:
                    tiket.lolos_qc = lolos_qc
                    update_fields.append('lolos_qc')
                    changed = True
                if tidak_lolos_qc is not None and tiket.tidak_lolos_qc != tidak_lolos_qc:
                    tiket.tidak_lolos_qc = tidak_lolos_qc
                    update_fields.append('tidak_lolos_qc')
                    changed = True
                if qc_p is not None and tiket.qc_p != qc_p:
                    tiket.qc_p = qc_p
                    update_fields.append('qc_p')
                    changed = True
                if qc_x is not None and tiket.qc_x != qc_x:
                    tiket.qc_x = qc_x
                    update_fields.append('qc_x')
                    changed = True
                if qc_w is not None and tiket.qc_w != qc_w:
                    tiket.qc_w = qc_w
                    update_fields.append('qc_w')
                    changed = True
                if qc_f is not None and tiket.qc_f != qc_f:
                    tiket.qc_f = qc_f
                    update_fields.append('qc_f')
                    changed = True
                if qc_a is not None and tiket.qc_a != qc_a:
                    tiket.qc_a = qc_a
                    update_fields.append('qc_a')
                    changed = True
                if qc_c is not None and tiket.qc_c != qc_c:
                    tiket.qc_c = qc_c
                    update_fields.append('qc_c')
                    changed = True
                if qc_n is not None and tiket.qc_n != qc_n:
                    tiket.qc_n = qc_n
                    update_fields.append('qc_n')
                    changed = True
                if qc_y is not None and tiket.qc_y != qc_y:
                    tiket.qc_y = qc_y
                    update_fields.append('qc_y')
                    changed = True
                if qc_z is not None and tiket.qc_z != qc_z:
                    tiket.qc_z = qc_z
                    update_fields.append('qc_z')
                    changed = True
                if qc_u is not None and tiket.qc_u != qc_u:
                    tiket.qc_u = qc_u
                    update_fields.append('qc_u')
                    changed = True
                if qc_e is not None and tiket.qc_e != qc_e:
                    tiket.qc_e = qc_e
                    update_fields.append('qc_e')
                    changed = True
                if qc_v is not None and tiket.qc_v != qc_v:
                    tiket.qc_v = qc_v
                    update_fields.append('qc_v')
                    changed = True
                if qc_r is not None and tiket.qc_r != qc_r:
                    tiket.qc_r = qc_r
                    update_fields.append('qc_r')
                    changed = True
                if qc_d is not None and tiket.qc_d != qc_d:
                    tiket.qc_d = qc_d
                    update_fields.append('qc_d')
                    changed = True

                # Status transitions
                needs_pmde_transition = (
                    tiket.status_tiket == STATUS_IDENTIFIKASI
                    and tgl_transfer is not None
                    and baris_i is not None
                    and baris_i > 0
                    and (belum_qc is None or belum_qc != 0)
                )
                needs_selesai_transition = (
                    tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
                    and belum_qc is not None
                    and belum_qc == 0
                )
                needs_selesai_from_5_transition = (
                    tiket.status_tiket == STATUS_IDENTIFIKASI
                    and tgl_transfer is not None
                    and belum_qc is not None
                    and belum_qc == 0
                )
                needs_dikembalikan_transition = (
                    tiket.status_tiket == STATUS_IDENTIFIKASI
                    and tgl_transfer is not None
                    and baris_i is not None and baris_i == 0
                    and baris_u is not None and baris_u == 0
                    and baris_res is not None and baris_res == 0
                    and baris_cde is not None and baris_cde > 0
                )
                needs_selesai_from_5_baris_transition = (
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

                if needs_pmde_transition:
                    update_fields.append('status_tiket')
                    tiket.status_tiket = STATUS_PENGENDALIAN_MUTU
                    changed = True
                if needs_selesai_transition:
                    update_fields.append('status_tiket')
                    tiket.status_tiket = STATUS_SELESAI
                    changed = True
                if needs_selesai_from_5_transition:
                    update_fields.append('status_tiket')
                    tiket.status_tiket = STATUS_SELESAI
                    changed = True
                if needs_dikembalikan_transition:
                    update_fields.append('status_tiket')
                    tiket.status_tiket = STATUS_DIKEMBALIKAN
                    update_fields.append('tgl_dikembalikan')
                    tiket.tgl_dikembalikan = tgl_transfer or timezone.now()
                    update_fields.append('tgl_rekam_pide')
                    tiket.tgl_rekam_pide = None
                    changed = True
                if needs_selesai_from_5_baris_transition:
                    update_fields.append('status_tiket')
                    tiket.status_tiket = STATUS_SELESAI
                    changed = True

                if not changed:
                    unchanged_count += 1
                    _log_update_result_row(
                        sync_id, nomor_tiket,
                        'Tidak Berubah',
                        'Data sudah sinkron, tidak ada perubahan'
                    )
                    continue

                tiket.save(update_fields=list(set(update_fields)))
                updated_rows += 1
                if len(updated_keys) < 5:
                    updated_keys.append(nomor_tiket)

                # Log field updates detail
                updated_field_names = list(set(update_fields) - {'status_tiket'})
                detail_parts = []
                if updated_field_names:
                    detail_parts.append(f"Field: {', '.join(updated_field_names)}")
                if needs_pmde_transition:
                    detail_parts.append(f"I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde}")

                _log_update_result_row(
                    sync_id, nomor_tiket,
                    'Baris Diupdate',
                    ' | '.join(detail_parts) if detail_parts else 'Data diperbarui'
                )

                if needs_pmde_transition:
                    status_to_pmde += 1
                    tiket_pics = active_pics_map.get(tiket.id, {})
                    pide_pics = tiket_pics.get(TiketPIC.Role.PIDE, [])
                    action_user = pide_pics[0].id_user if pide_pics else None
                    if action_user:
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=action_user,
                            timestamp=tgl_transfer or timezone.now(),
                            action=TiketActionType.DITRANSFER_KE_PMDE,
                            catatan='Tiket ditransfer ke PMDE'
                        )
                        logger.info(f'Tiket {nomor_tiket}: {STATUS_IDENTIFIKASI} → {STATUS_PENGENDALIAN_MUTU} (auto-transfer, user={action_user.username})')
                    else:
                        logger.warning(f'Tiket {nomor_tiket}: no active PIDE PIC — status updated but no TiketAction')

                    _log_update_result_row(
                        sync_id, nomor_tiket,
                        'Status → Pengendalian Mutu',
                        f'Dari IDENTIFIKASI ke PENGENDALIAN_MUTU (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})'
                    )

                if needs_selesai_transition:
                    status_to_selesai += 1
                    tiket_pics = active_pics_map.get(tiket.id, {})
                    pmde_pics = tiket_pics.get(TiketPIC.Role.PMDE, [])
                    action_user = pmde_pics[0].id_user if pmde_pics else None
                    if action_user:
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=action_user,
                            timestamp=tgl_transfer or timezone.now(),
                            action=TiketActionType.PENGENDALIAN_MUTU,
                            catatan='Tiket selesai pengendalian mutu'
                        )
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=action_user,
                            timestamp=tgl_close_tiket or timezone.now(),
                            action=TiketActionType.SELESAI,
                            catatan='Tiket selesai diproses)'
                        )
                        logger.info(f'Tiket {nomor_tiket}: {STATUS_PENGENDALIAN_MUTU} → {STATUS_SELESAI} (auto-complete, user={action_user.username})')
                    else:
                        logger.warning(f'Tiket {nomor_tiket}: no active PMDE PIC — status updated but no TiketAction')

                    _log_update_result_row(
                        sync_id, nomor_tiket,
                        'Status → Selesai',
                        f'Dari PENGENDALIAN_MUTU ke SELESAI (Sudah QC:{sudah_qc}, Lolos QC:{lolos_qc}, Tidak Lolos QC:{tidak_lolos_qc})'
                    )

                if needs_selesai_from_5_transition:
                    status_to_selesai += 1
                    tiket_pics = active_pics_map.get(tiket.id, {})
                    pide_pics = tiket_pics.get(TiketPIC.Role.PIDE, [])
                    pmde_pics = tiket_pics.get(TiketPIC.Role.PMDE, [])
                    pide_user = pide_pics[0].id_user if pide_pics else None
                    pmde_user = pmde_pics[0].id_user if pmde_pics else None
                    if pide_user:
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=pide_user,
                            timestamp=tgl_transfer or timezone.now(),
                            action=TiketActionType.DITRANSFER_KE_PMDE,
                            catatan='Tiket ditransfer ke PMDE'
                        )
                    else:
                        logger.warning(f'Tiket {nomor_tiket}: no active PIDE PIC — DITRANSFER_KE_PMDE action skipped')
                    if pmde_user:
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=pmde_user,
                            timestamp=tgl_transfer or timezone.now(),
                            action=TiketActionType.PENGENDALIAN_MUTU,
                            catatan='Tiket selesai pengendalian mutu'
                        )
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=pmde_user,
                            timestamp=tgl_close_tiket or timezone.now(),
                            action=TiketActionType.SELESAI,
                            catatan='Tiket selesai diproses'
                        )
                        logger.info(f'Tiket {nomor_tiket}: {STATUS_IDENTIFIKASI} → {STATUS_SELESAI} (langsung, pide={pide_user.username if pide_user else None}, pmde={pmde_user.username})')
                    else:
                        logger.warning(f'Tiket {nomor_tiket}: no active PMDE PIC — PENGENDALIAN_MUTU & SELESAI actions skipped')

                    _log_update_result_row(
                        sync_id, nomor_tiket,
                        'Status → Selesai (langsung dari Identifikasi)',
                        f'Dari IDENTIFIKASI langsung ke SELESAI (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde}, Sudah QC:{sudah_qc})'
                    )

                if needs_dikembalikan_transition:
                    status_to_dikembalikan += 1
                    tiket_pics = active_pics_map.get(tiket.id, {})
                    pide_pics = tiket_pics.get(TiketPIC.Role.PIDE, [])
                    p3de_pics = tiket_pics.get(TiketPIC.Role.P3DE, [])
                    pide_user = pide_pics[0].id_user if pide_pics else None
                    p3de_user = p3de_pics[0].id_user if p3de_pics else None

                    if pide_user:
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=pide_user,
                            timestamp=tgl_transfer or timezone.now(),
                            action=TiketActionType.DIKEMBALIKAN,
                            catatan='Tiket dikembalikan oleh PIDE (auto-sync)'
                        )
                    else:
                        logger.warning(f'Tiket {nomor_tiket}: no active PIDE PIC — DIKEMBALIKAN action skipped')

                    if p3de_user:
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=p3de_user,
                            timestamp=tgl_transfer or timezone.now(),
                            action=TiketActionType.DIBATALKAN,
                            catatan='Tiket dibatalkan (dikembalikan oleh PIDE: auto-sync)'
                        )
                        logger.info(f'Tiket {nomor_tiket}: {STATUS_IDENTIFIKASI} → {STATUS_DIKEMBALIKAN} (pide={pide_user.username if pide_user else None}, p3de={p3de_user.username})')
                    else:
                        logger.warning(f'Tiket {nomor_tiket}: no active P3DE PIC — DIBATALKAN action skipped')

                    # Send notification to active P3DE PICs
                    for pic in p3de_pics:
                        Notification.objects.create(
                            recipient=pic.id_user,
                            title='Tiket Dikembalikan',
                            message=f'Tiket {nomor_tiket} telah dikembalikan oleh PIDE (auto-sync)'
                        )

                    _log_update_result_row(
                        sync_id, nomor_tiket,
                        'Status → Dikembalikan',
                        f'Dari IDENTIFIKASI ke DIKEMBALIKAN (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})'
                    )

                if needs_selesai_from_5_baris_transition:
                    status_to_selesai += 1
                    tiket_pics = active_pics_map.get(tiket.id, {})
                    pide_pics = tiket_pics.get(TiketPIC.Role.PIDE, [])
                    pmde_pics = tiket_pics.get(TiketPIC.Role.PMDE, [])
                    pide_user = pide_pics[0].id_user if pide_pics else None
                    pmde_user = pmde_pics[0].id_user if pmde_pics else None
                    if pide_user:
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=pide_user,
                            timestamp=tgl_transfer or timezone.now(),
                            action=TiketActionType.DITRANSFER_KE_PMDE,
                            catatan='Tiket ditransfer ke PMDE'
                        )
                    else:
                        logger.warning(f'Tiket {nomor_tiket}: no active PIDE PIC — DITRANSFER_KE_PMDE action skipped')
                    if pmde_user:
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=pmde_user,
                            timestamp=tgl_transfer or timezone.now(),
                            action=TiketActionType.PENGENDALIAN_MUTU,
                            catatan='Tiket selesai pengendalian mutu'
                        )
                        TiketAction.objects.create(
                            id_tiket=tiket, id_user=pmde_user,
                            timestamp=tgl_close_tiket or timezone.now(),
                            action=TiketActionType.SELESAI,
                            catatan='Tiket selesai diproses'
                        )
                        logger.info(f'Tiket {nomor_tiket}: {STATUS_IDENTIFIKASI} → {STATUS_SELESAI} (langsung-baris, pide={pide_user.username if pide_user else None}, pmde={pmde_user.username})')
                    else:
                        logger.warning(f'Tiket {nomor_tiket}: no active PMDE PIC — PENGENDALIAN_MUTU & SELESAI actions skipped')

                    _log_update_result_row(
                        sync_id, nomor_tiket,
                        'Status → Selesai (langsung dari Identifikasi - baris)',
                        f'Dari IDENTIFIKASI langsung ke SELESAI (I:{baris_i}, U:{baris_u}, Res:{baris_res}, CDE:{baris_cde})'
                    )

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
            'updated_rows': updated_rows,
            'status_to_pmde': status_to_pmde,
            'status_to_selesai': status_to_selesai,
            'status_to_dikembalikan': status_to_dikembalikan,
            'not_found': not_found_count,
            'unchanged': unchanged_count,
            'errors': errors,
            'updated_keys': updated_keys,
        }
    except Exception as e:
        logger.error(f'Tiket update sync failed: {str(e)}', exc_info=True)
        return {
            'updated_rows': 0, 'status_to_pmde': 0, 'status_to_selesai': 0,
            'status_to_dikembalikan': 0, 'not_found': 0, 'unchanged': 0,
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
                'would_update': 0, 'would_pmde': 0, 'would_selesai': 0, 'errors': 0,
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
            'updated_rows': 0, 'status_to_pmde': 0, 'status_to_selesai': 0, 'errors': 0,
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
                    'message': f"Update selesai: {result.get('updated_rows', 0)} diupdate, {result.get('status_to_pmde', 0)} → PMDE, {result.get('status_to_selesai', 0)} → Selesai",
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
