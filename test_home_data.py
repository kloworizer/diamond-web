import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "diamond_web.settings")
django.setup()

from diamond_web.models.tiket import Tiket
from diamond_web.views.home import _get_p3de_tiket_ids, STATUS_DIREKAM

# simulate the query for belum_rekam_backup_data
qs = Tiket.objects.filter(status_tiket=STATUS_DIREKAM, backup=False)
qs = qs.order_by('-id')[:10]
for obj in qs:
    print(f"Ticket ID {obj.pk}: baris_diterima={obj.baris_diterima}")
