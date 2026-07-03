import uuid
import logging
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError
from ...views.sync_tiket_update import _update_tiket_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Update tiket QC/transfer columns from Oracle and apply status transitions"

    def handle(self, *args, **options):
        try:
            service = OracleDataSyncService(connection_only=True)
            sync_id = str(uuid.uuid4())

            start_time = timezone.now()
            self.stdout.write(f"Mulai update tiket (sync_id={sync_id})...")

            summary = _update_tiket_data(service, sync_id=sync_id)

            elapsed = (timezone.now() - start_time).total_seconds()
            self.stdout.write(self.style.SUCCESS('Update tiket selesai.'))
            self.stdout.write(f"- Baris diupdate     : {summary.get('updated_rows', 0)}")
            self.stdout.write(f"- Status → PMDE      : {summary.get('status_to_pmde', 0)}")
            self.stdout.write(f"- Status → SELESAI   : {summary.get('status_to_selesai', 0)}")
            self.stdout.write(f"- Waktu eksekusi     : {elapsed:.1f} detik")

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

        except OracleSyncConfigError as exc:
            raise CommandError(str(exc)) from exc
