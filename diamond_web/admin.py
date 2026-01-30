from django.contrib import admin
from .models import Notification, TandaTerimaData, DetilTandaTerima, BackupData

admin.site.register(Notification)
admin.site.register(TandaTerimaData)
admin.site.register(DetilTandaTerima)
admin.site.register(BackupData)
