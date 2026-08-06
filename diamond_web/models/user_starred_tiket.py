from django.db import models
from django.contrib.auth.models import User

class UserStarredTiket(models.Model):
    """
    Menyimpan daftar tiket pantauan (watchlist) untuk masing-masing user.
    """
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="id_user",
        verbose_name="User"
    )
    nomor_tiket = models.CharField(max_length=17, verbose_name="Nomor Tiket")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "User Starred Tiket"
        verbose_name_plural = "User Starred Tikets"
        db_table = "user_starred_tiket"
        ordering = ["-created_at"]
        unique_together = ('id_user', 'nomor_tiket')

    def __str__(self):
        return f"{self.id_user.username} - {self.nomor_tiket}"
