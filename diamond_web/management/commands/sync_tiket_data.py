import uuid
import logging
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError
from ...views.sync_tiket import _sync_tiket_data, _check_tiket_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sync tiket data dari Oracle ke Django models"

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Hanya cek perubahan tanpa insert/update ke DB aplikasi',
        )

    def handle(self, *args, **options):
        check_only = options.get('check_only', False)

        try:
            service = OracleDataSyncService(connection_only=True)
            sync_id = str(uuid.uuid4())

            start_time = timezone.now()
            self.stdout.write(f"Mulai {'check' if check_only else 'sync'} tiket (sync_id={sync_id})...")

            if check_only:
                summary = _check_tiket_data(service, check_id=sync_id)
                self.stdout.write(self.style.SUCCESS('Check tiket selesai.'))
                self.stdout.write(f"- Source rows : {summary.get('source_rows', 0)}")
                self.stdout.write(f"- Akan insert : {summary.get('inserts', 0)}")
                self.stdout.write(f"- Akan update : {summary.get('updates', 0)}")
                self.stdout.write(f"- Tidak berubah: {summary.get('unchanged', 0)}")
            else:
                summary = _sync_tiket_data(service, sync_id=sync_id)
                elapsed = (timezone.now() - start_time).total_seconds()
                self.stdout.write(self.style.SUCCESS('Sync tiket selesai.'))
                self.stdout.write(f"- Source rows : {summary.get('source_rows', 0)}")
                self.stdout.write(f"- Inserts     : {summary.get('inserts', 0)}")
                self.stdout.write(f"- Updates     : {summary.get('updates', 0)}")
                self.stdout.write(f"- Tidak berubah: {summary.get('unchanged', 0)}")
                self.stdout.write(f"- Waktu eksekusi: {elapsed:.1f} detik")

            errors = summary.get('errors', [])
            if errors:
                self.stdout.write(self.style.WARNING(f'Error ({len(errors)}):'))
                for err in errors[:20]:
                    self.stdout.write(f"  - {err}")
                if len(errors) > 20:
                    self.stdout.write(f"  ... dan {len(errors) - 20} error lainnya")
                self.stdout.write(self.style.WARNING('Sync tetap dilanjutkan. Error sudah dicatat di log.'))

            if check_only:
                self.stdout.write(self.style.WARNING('Mode check-only: tidak ada perubahan DB.'))

        except OracleSyncConfigError as exc:
            raise CommandError(str(exc)) from exc
