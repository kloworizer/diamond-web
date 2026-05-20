from django.core.management.base import BaseCommand, CommandError

from ...utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError


class Command(BaseCommand):
    help = "Sync data dari Oracle ke tabel Django berdasarkan hardcoded mapping di utils/oracle_sync.py"

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Hanya cek perubahan tanpa insert/update ke DB aplikasi',
        )

    def handle(self, *args, **options):
        check_only = options.get('check_only', False)

        try:
            service = OracleDataSyncService()
            summary = service.check() if check_only else service.sync()

            self.stdout.write(self.style.SUCCESS('Oracle sync selesai.'))
            self.stdout.write(f"- Source rows : {summary.source_rows}")
            self.stdout.write(f"- Inserts     : {summary.inserts}")
            self.stdout.write(f"- Updates     : {summary.updates}")
            self.stdout.write(f"- Unchanged   : {summary.unchanged}")

            if summary.errors:
                self.stdout.write(self.style.ERROR('Error data ditemukan:'))
                for err in summary.errors:
                    self.stdout.write(f"  - {err}")
                raise CommandError('Sync dibatalkan karena ada error data.')

            if check_only:
                self.stdout.write(self.style.WARNING('Mode check-only: tidak ada perubahan DB.'))

        except OracleSyncConfigError as exc:
            raise CommandError(str(exc)) from exc