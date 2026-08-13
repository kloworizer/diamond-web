"""Bulk Teliti endpoint — batch version of RekamHasilPenelitianView."""
import json
from datetime import datetime
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...models.status_penelitian import StatusPenelitian
from ...constants.tiket_action_types import TiketActionType
from ...constants.tiket_status import STATUS_DITELITI, STATUS_SELESAI
from ..mixins import UserP3DERequiredMixin


class BulkTelitianView(LoginRequiredMixin, UserP3DERequiredMixin, View):
    """Batch version of RekamHasilPenelitianView.

    Accepts a JSON list of per-tiket research results and applies
    the same status calculation logic as the single-tiket view.

    POST body (JSON):
    [
      {
        "tiket_id": 42,
        "baris_diterima": 100,
        "baris_lengkap": 80,
        "tgl_teliti": "2026-08-09",
        "catatan": ""
      },
      ...
    ]

    Access Control:
    - @login_required
    - user must be in user_p3de group
    - user must be active P3DE PIC for EACH tiket (checked per-row)

    Returns JSON: { success, updated, skipped, errors }
    """

    def post(self, request, *args, **kwargs):
        try:
            items = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'success': False, 'message': 'Payload tidak valid.'}, status=400)

        updated, skipped, errors = [], [], []
        now = datetime.now()

        for item in items:
            tiket_id     = item.get('tiket_id')
            baris_terima = int(item.get('baris_diterima') or 0)
            baris_lengkap = int(item.get('baris_lengkap') or 0)
            tgl_teliti   = item.get('tgl_teliti')
            catatan      = item.get('catatan', '') or 'Hasil penelitian direkam (bulk)'

            # Validate tiket existence and PIC ownership
            try:
                tiket = Tiket.objects.get(pk=tiket_id)
            except Tiket.DoesNotExist:
                errors.append({'tiket_id': tiket_id, 'error': 'Tiket tidak ditemukan.'})
                continue

            is_active_pic = TiketPIC.objects.filter(
                id_tiket=tiket, id_user=request.user, active=True, role=TiketPIC.Role.P3DE
            ).exists()
            
            if not is_active_pic:
                skipped.append(tiket_id)
                continue

            # Replicate logic from RekamHasilPenelitianView.form_valid()
            tiket.baris_diterima = baris_terima
            tiket.baris_lengkap  = baris_lengkap
            
            try:
                if baris_lengkap == baris_terima:
                    tiket.id_status_penelitian = StatusPenelitian.objects.get(deskripsi='Lengkap')
                    tiket.status_tiket = STATUS_DITELITI
                elif baris_lengkap == 0:
                    tiket.id_status_penelitian = StatusPenelitian.objects.get(deskripsi='Tidak Lengkap')
                    tiket.status_tiket = STATUS_SELESAI
                else:
                    tiket.id_status_penelitian = StatusPenelitian.objects.get(deskripsi='Lengkap Sebagian')
                    tiket.status_tiket = STATUS_DITELITI
            except StatusPenelitian.DoesNotExist:
                tiket.status_tiket = STATUS_DITELITI

            if tgl_teliti:
                tiket.tgl_teliti = tgl_teliti
                
            tiket.save()

            TiketAction.objects.create(
                id_tiket=tiket, id_user=request.user,
                timestamp=now, action=TiketActionType.DITELITI, catatan=catatan
            )
            
            if tiket.status_tiket == STATUS_SELESAI:
                TiketAction.objects.create(
                    id_tiket=tiket, id_user=request.user,
                    timestamp=now, action=TiketActionType.SELESAI, catatan='Tiket selesai diproses'
                )

            updated.append(tiket_id)

        return JsonResponse({
            'success': True,
            'updated': len(updated),
            'skipped': len(skipped),
            'errors': errors,
            'message': f'{len(updated)} tiket berhasil diteliti.'
        })
