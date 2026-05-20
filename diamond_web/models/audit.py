from django.db import models


class AuditTrailModel(models.Model):
    create_date = models.DateField(null=True, blank=True, verbose_name="Create Date")
    create_by = models.CharField(max_length=9, null=True, blank=True, verbose_name="Create By")
    update_date = models.DateField(null=True, blank=True, verbose_name="Update Date")
    update_by = models.CharField(max_length=9, null=True, blank=True, verbose_name="Update By")

    class Meta:
        abstract = True
