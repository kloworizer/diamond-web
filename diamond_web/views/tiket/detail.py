"""Tiket Detail View"""

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...models.jenis_prioritas_data import JenisPrioritasData
from ...models.klasifikasi_jenis_data import KlasifikasiJenisData
from ...models.detil_tanda_terima import DetilTandaTerima
from .base import WorkflowStepDetailView


class TiketDetailView(WorkflowStepDetailView):
    """Detail view for viewing a tiket."""
    model = Tiket
    template_name = 'tiket/tiket_detail.html'
    context_object_name = 'tiket'
    
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
        
        # Define status labels and badge classes
        status_labels = {
            1: 'Direkam',
            2: 'Backup direkam',
            3: 'Tanda Terima dibuat',
            4: 'Diteliti',
            5: 'Dikembalikan',
            6: 'Dikirim ke PIDE',
            7: 'Identifikasi',
            8: 'Pengendalian Mutu',
            9: 'Dibatalkan',
            10: 'Selesai'
        }
        
        status_badge_classes = {
            1: 'bg-primary',
            2: 'bg-info',
            3: 'bg-success',
            4: 'bg-secondary',
            5: 'bg-info',
            6: 'bg-warning text-dark',
            7: 'bg-info',
            8: 'bg-secondary',
            9: 'bg-danger',
            10: 'bg-success'
        }
        
        action_badges = {
            1: {'label': 'Direkam', 'class': 'bg-primary'},
            2: {'label': 'Backup direkam', 'class': 'bg-info'},
            3: {'label': 'Tanda Terima dibuat', 'class': 'bg-success'},
            4: {'label': 'Diteliti', 'class': 'bg-secondary'},
            5: {'label': 'Dikembalikan', 'class': 'bg-info'},
            6: {'label': 'Dikirim ke PIDE', 'class': 'bg-warning'},
            7: {'label': 'Identifikasi', 'class': 'bg-info'},
            8: {'label': 'Pengendalian Mutu', 'class': 'bg-secondary'},
            9: {'label': 'Dibatalkan', 'class': 'bg-danger'},
            10: {'label': 'Selesai', 'class': 'bg-success'}
        }
        
        role_badges = {
            1: {'label': 'Admin', 'class': 'bg-success'},
            2: {'label': 'P3DE', 'class': 'bg-primary'},
            3: {'label': 'PIDE', 'class': 'bg-info'},
            4: {'label': 'PMDE', 'class': 'bg-warning text-dark'}
        }
        
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
        
        # Check if has prioritas
        has_prioritas = JenisPrioritasData.objects.filter(
            id_sub_jenis_data_ilap=jenis_data
        ).exists()
        
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
            'has_prioritas': 'Ya' if has_prioritas else 'Tidak',
            'klasifikasi': klasifikasi_items,
        }
        
        # Add formatted periode to context
        context['periode_formatted'] = periode_formatted
        
        # Get actions and enrich with badge info
        tiket_actions = TiketAction.objects.filter(
            id_tiket=self.object
        ).select_related('id_user').order_by('-timestamp')
        
        for action in tiket_actions:
            badge = action_badges.get(action.action, {'label': str(action.action), 'class': 'bg-secondary'})
            action.badge_label = badge['label']
            action.badge_class = badge['class']
            full_name = (action.id_user.get_full_name() or '').strip()
            action.user_display = (
                f"{action.id_user.username} - {full_name}"
                if full_name else action.id_user.username
            )
        
        # Get PICs and enrich with badge info
        tiket_pics = TiketPIC.objects.filter(
            id_tiket=self.object
        ).select_related('id_user').order_by('-timestamp')
        
        for pic in tiket_pics:
            badge = role_badges.get(pic.role, {'label': str(pic.role), 'class': 'bg-info'})
            pic.badge_label = badge['label']
            pic.badge_class = badge['class']
            full_name = (pic.id_user.get_full_name() or '').strip()
            pic.user_display = (
                f"{pic.id_user.username} - {full_name}"
                if full_name else pic.id_user.username
            )
        
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
        context['status_label'] = status_labels.get(self.object.status, '-')
        context['status_badge_class'] = status_badge_classes.get(self.object.status, 'bg-secondary')
        context['page_title'] = f'Detail Tiket {self.object.nomor_tiket}'
        
        # Get workflow step based on status
        workflow_steps = {
            1: 'rekam',
            2: 'backup',
            3: 'tanda_terima',
            4: 'teliti',
            5: 'kembali',
            6: 'kirim_pide',
            7: 'identifikasi',
            8: 'pengendalian_mutu',
            9: 'batal',
            10: 'selesai'
        }
        context['workflow_step'] = workflow_steps.get(self.object.status, 'rekam')
        return context
