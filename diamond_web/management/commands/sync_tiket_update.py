import os
import uuid
import logging
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError
from ...views.sync_tiket_update import _update_tiket_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Update tiket QC/transfer columns from Oracle and apply status transitions, "
        "then refresh KD Tahap for the tikets that changed"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--tanpa-kd-tahap', action='store_true',
            help='Jangan sinkronkan KD Tahap untuk tiket yang berubah setelah update.',
        )

    def handle(self, *args, **options):
        try:
            service = OracleDataSyncService(connection_only=True)
            sync_id = str(uuid.uuid4())

            start_time = timezone.now()
            self.stdout.write(f"Mulai update tiket (sync_id={sync_id})...")

            summary = _update_tiket_data(service, sync_id=sync_id)

            elapsed = (timezone.now() - start_time).total_seconds()
            self.stdout.write(self.style.SUCCESS('Update tiket selesai.'))
            self.stdout.write(f"- Baris diupdate       : {summary.get('updated_rows', 0)}")
            self.stdout.write(f"- Tidak berubah        : {summary.get('unchanged', 0)}")
            self.stdout.write(f"- Belum disinkronisasi : {summary.get('not_found', 0)}")
            self.stdout.write(f"- Status → PMDE        : {summary.get('status_to_pmde', 0)}")
            self.stdout.write(f"- Status → SELESAI     : {summary.get('status_to_selesai', 0)}")
            self.stdout.write(f"- Waktu eksekusi       : {elapsed:.1f} detik")

            errors = summary.get('errors', [])
            if errors:
                self.stdout.write(self.style.WARNING(f'Error ({len(errors)}):'))
                for err in errors[:20]:
                    self.stdout.write(f"  - {err}")
                if len(errors) > 20:
                    self.stdout.write(f"  ... dan {len(errors) - 20} error lainnya")
                self.stdout.write(self.style.WARNING('Update tetap dilanjutkan. Error sudah dicatat di log.'))

            updated_keys = summary.get('updated_keys', [])
            if updated_keys:
                self.stdout.write(f"Contoh tiket diupdate: {', '.join(updated_keys[:5])}")

            from ...views.sync_tiket_update import SYNC_LOGS_DIR
            result_log = os.path.join(SYNC_LOGS_DIR, f'tiket_update_result_{sync_id}.csv')
            self.stdout.write(f"Detail log: {result_log}")

        except OracleSyncConfigError as exc:
            raise CommandError(str(exc)) from exc

        if not options['tanpa_kd_tahap']:
            self._sinkron_kd_tahap(summary.get('changed_tikets', []))

    def _sinkron_kd_tahap(self, nomor_tikets):
        """Refresh KD Tahap for the tikets this update changed.

        Their QC / baris counts moved, so their rows per KD Tahap & QC may have
        too. `sync_tiket_kd_tahap` keeps only those now at Pengendalian Mutu or
        Selesai and writes its own log to sync_logs/. A failure here leaves the
        tiket update, already saved, as it is.
        """
        self.stdout.write('')
        if not nomor_tikets:
            self.stdout.write('KD Tahap: tidak ada tiket yang berubah, tidak ada yang disinkronkan.')
            return
        self.stdout.write(f'Sinkronisasi KD Tahap untuk {len(nomor_tikets)} tiket yang berubah...')
        try:
            call_command(
                'sync_tiket_kd_tahap', tiket=','.join(nomor_tikets),
                stdout=self.stdout, stderr=self.stderr,
            )
        except Exception as exc:  # CommandError (Oracle unreachable, ...) or unexpected
            logger.exception('KD Tahap setelah update tiket gagal')
            self.stdout.write(self.style.WARNING(
                f'Sinkronisasi KD Tahap gagal: {exc}. Update tiket tetap tersimpan; '
                'detail ada di log "Sinkronisasi KD Tahap" di halaman Sync Log Status.'
            ))
