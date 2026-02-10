"""Tiket Detail View"""

from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...models.pic import PIC
from ...models.klasifikasi_jenis_data import KlasifikasiJenisData
from ...models.detil_tanda_terima import DetilTandaTerima
from ...constants.tiket_status import STATUS_LABELS, STATUS_BADGE_CLASSES
from ...constants.tiket_action_types import (
    ACTION_BADGES,
    ROLE_BADGES,
    WORKFLOW_STEPS,
    get_action_label,
    get_action_badge_class,
)


class TiketDetailView(LoginRequiredMixin, DetailView):
    """Detail view for viewing a tiket."""
    model = Tiket
    template_name = 'tiket/tiket_detail.html'
    context_object_name = 'tiket'

    def get_object(self, queryset=None):
        """Override to ensure user is a PIC for this tiket (active or inactive) or is admin"""
        obj = super().get_object(queryset)
        # Allow access if user is superuser or admin
        if self.request.user.is_superuser or self.request.user.groups.filter(name='admin').exists():
            return obj
        # Allow access if user is any kind of PIC for this tiket (active or inactive)
        if not TiketPIC.objects.filter(id_tiket=obj, id_user=self.request.user).exists():
            raise PermissionDenied()
        return obj

    
    def _format_periode(self, deskripsi_periode, periode, tahun):
        """Format periode based on deskripsi periode type."""
        bulan_names = [
            'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
        ]
        
        if deskripsi_periode == 'Harian':
            return f'Hari {periode} - {tahun}'
        elif deskripsi_periode == 'Mingguan':
            return f'Minggu {periode} - {tahun}'
        elif deskripsi_periode == '2 Mingguan':
            return f'2 Minggu {periode} - {tahun}'
        elif deskripsi_periode == 'Bulanan':
            if 1 <= periode <= 12:
                return f'{bulan_names[periode - 1]} {tahun}'
            return f'Bulan {periode} - {tahun}'
        elif deskripsi_periode == 'Triwulanan':
            return f'Triwulan {periode} - {tahun}'
        elif deskripsi_periode == 'Kuartal':
            return f'Kuartal {periode} - {tahun}'
        elif deskripsi_periode == 'Semester':
            return f'Semester {periode} - {tahun}'
        elif deskripsi_periode == 'Tahunan':
            return str(tahun)
        else:
            return f'{periode} - {tahun}'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get related data
        periode_jenis_data = self.object.id_periode_data
        jenis_data = periode_jenis_data.id_sub_jenis_data_ilap
        ilap = jenis_data.id_ilap
        
        # Get klasifikasi
        try:
            klasifikasi_list = KlasifikasiJenisData.objects.filter(
                id_jenis_data_ilap=jenis_data
            ).select_related('id_klasifikasi_tabel')
            klasifikasi_items = [item.id_klasifikasi_tabel.deskripsi for item in klasifikasi_list]
        except Exception:
            klasifikasi_items = []
        
        # Jenis prioritas from tiket (transaction)
        jenis_prioritas_text = 'Ya' if self.object.id_jenis_prioritas_data else 'Tidak'
        
        # Format periode based on deskripsi
        periode_formatted = self._format_periode(
            periode_jenis_data.id_periode_pengiriman.deskripsi,
            self.object.periode,
            self.object.tahun
        )
        
        # Prepare ILAP information
        context['ilap_info'] = {
            'nama_ilap': ilap.nama_ilap,
            'kategori_ilap': ilap.id_kategori.nama_kategori if ilap.id_kategori else '-',
            'kategori_wilayah': ilap.id_kategori_wilayah.deskripsi if ilap.id_kategori_wilayah else '-',
            'id_sub_jenis_data': jenis_data.id_sub_jenis_data,
            'nama_sub_jenis_data': jenis_data.nama_sub_jenis_data,
            'jenis_tabel': jenis_data.id_jenis_tabel.deskripsi if jenis_data.id_jenis_tabel else '-',
            'deskripsi_periode': periode_jenis_data.id_periode_pengiriman.deskripsi,
            'jenis_prioritas': jenis_prioritas_text,
            'klasifikasi': klasifikasi_items,
        }
        
        # Add formatted periode to context
        context['periode_formatted'] = periode_formatted
        
        # Get actions and enrich with badge info
        tiket_actions = TiketAction.objects.filter(
            id_tiket=self.object
        ).select_related('id_user').order_by('-timestamp')
        
        for action in tiket_actions:
            action.badge_label = get_action_label(action.action)
            action.badge_class = get_action_badge_class(action.action)
            full_name = (action.id_user.get_full_name() or '').strip()
            action.user_display = (
                f"{action.id_user.username} - {full_name}"
                if full_name else action.id_user.username
            )
        
        # Get PICs and enrich with badge info
        tiket_pics = TiketPIC.objects.filter(
            id_tiket=self.object
        ).select_related('id_user').order_by('role', 'id_user__username')

        for pic in tiket_pics:
            badge = ROLE_BADGES.get(pic.role, {'label': str(pic.role), 'class': 'bg-info'})
            pic.badge_label = badge['label']
            pic.badge_class = badge['class']
            full_name = (pic.id_user.get_full_name() or '').strip()
            pic.user_display = (
                f"{pic.id_user.username} - {full_name}"
                if full_name else pic.id_user.username
            )
            
            # Check if this PIC is active (has an active PIC record without end_date)
            if pic.role == TiketPIC.Role.P3DE:
                tipe = PIC.TipePIC.P3DE
            elif pic.role == TiketPIC.Role.PIDE:
                tipe = PIC.TipePIC.PIDE
            elif pic.role == TiketPIC.Role.PMDE:
                tipe = PIC.TipePIC.PMDE
            else:
                tipe = None
            
            if tipe:
                pic.is_pic_active = PIC.objects.filter(
                    tipe=tipe,
                    id_user=pic.id_user,
                    id_sub_jenis_data_ilap=self.object.id_periode_data.id_sub_jenis_data_ilap,
                    end_date__isnull=True
                ).exists()
            else:
                pic.is_pic_active = False
        
        # Backup data list
        backups = self.object.backups.select_related('id_user').all().order_by('-id')

        # Tanda terima list for this tiket
        tanda_terima_items = DetilTandaTerima.objects.filter(
            id_tiket=self.object
        ).select_related('id_tanda_terima', 'id_tanda_terima__id_ilap', 'id_tanda_terima__id_perekam').order_by('-id')

        context['tiket_actions'] = tiket_actions
        context['tiket_pics'] = tiket_pics
        context['backup_list'] = backups
        context['tanda_terima_items'] = tanda_terima_items
        context['status_label'] = STATUS_LABELS.get(self.object.status, '-')
        context['status_badge_class'] = STATUS_BADGE_CLASSES.get(self.object.status, 'bg-secondary')
        context['page_title'] = f'Detail Tiket {self.object.nomor_tiket}'
        
        # Get workflow step based on status
        context['workflow_step'] = WORKFLOW_STEPS.get(self.object.status, 'rekam')
        
        # Check if current user has any active PIC record for this tiket (per role)
        user_is_active_pic_p3de = TiketPIC.objects.filter(
            id_tiket=self.object,
            id_user=self.request.user,
            active=True,
            role=TiketPIC.Role.P3DE
        ).exists()

        user_is_active_pic_pide = TiketPIC.objects.filter(
            id_tiket=self.object,
            id_user=self.request.user,
            active=True,
            role=TiketPIC.Role.PIDE
        ).exists()

        user_is_active_pic_pmde = TiketPIC.objects.filter(
            id_tiket=self.object,
            id_user=self.request.user,
            active=True,
            role=TiketPIC.Role.PMDE
        ).exists()

        # overall active flag (any role)
        user_is_active_pic = user_is_active_pic_p3de or user_is_active_pic_pide or user_is_active_pic_pmde

        context['user_is_active_pic'] = user_is_active_pic
        context['user_is_active_pic_p3de'] = user_is_active_pic_p3de
        context['user_is_active_pic_pide'] = user_is_active_pic_pide
        context['user_is_active_pic_pmde'] = user_is_active_pic_pmde
        
        return context
