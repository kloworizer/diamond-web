from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .views.general import keep_alive, session_expired
from .jenis_prioritas_data import (
    JenisPrioritasDataListView,
    JenisPrioritasDataCreateView,
    JenisPrioritasDataUpdateView,
    JenisPrioritasDataDeleteView,
    jenis_prioritas_data_data
)   


urlpatterns = [
    path('', views.home, name='home'),
    path('keep-alive/', keep_alive, name='keep_alive'),
    path('session-expired/', session_expired, name='session_expired'),
    path('notifications/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/change_password_form.html', success_url=reverse_lazy('user_password_change_done')), name='user_password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/change_password_done.html'), name='user_password_change_done'),

    # === P3DE Section ===
    # Kategori ILAP URLs
    path('kategori-ilap/', views.KategoriILAPListView.as_view(), name='kategori_ilap_list'),
    path('kategori-ilap/data/', views.kategori_ilap_data, name='kategori_ilap_data'),
    path('kategori-ilap/create/', views.KategoriILAPCreateView.as_view(), name='kategori_ilap_create'),
    path('kategori-ilap/<str:pk>/update/', views.KategoriILAPUpdateView.as_view(), name='kategori_ilap_update'),
    path('kategori-ilap/<str:pk>/delete/', views.KategoriILAPDeleteView.as_view(), name='kategori_ilap_delete'),
    # ILAP URLs
    path('ilap/', views.ILAPListView.as_view(), name='ilap_list'),
    path('ilap/data/', views.ilap_data, name='ilap_data'),
    path('ilap/next-id/', views.get_next_ilap_id, name='get_next_ilap_id'),
    path('ilap/create/', views.ILAPCreateView.as_view(), name='ilap_create'),
    path('ilap/<str:pk>/update/', views.ILAPUpdateView.as_view(), name='ilap_update'),
    path('ilap/<str:pk>/delete/', views.ILAPDeleteView.as_view(), name='ilap_delete'),
    # Jenis Tabel URLs
    path('jenis-tabel/', views.JenisTabelListView.as_view(), name='jenis_tabel_list'),
    path('jenis-tabel/data/', views.jenis_tabel_data, name='jenis_tabel_data'),
    path('jenis-tabel/create/', views.JenisTabelCreateView.as_view(), name='jenis_tabel_create'),
    path('jenis-tabel/<int:pk>/update/', views.JenisTabelUpdateView.as_view(), name='jenis_tabel_update'),
    path('jenis-tabel/<int:pk>/delete/', views.JenisTabelDeleteView.as_view(), name='jenis_tabel_delete'),
    # Kategori Wilayah URLs
    path('kategori-wilayah/', views.KategoriWilayahListView.as_view(), name='kategori_wilayah_list'),
    path('kategori-wilayah/data/', views.kategori_wilayah_data, name='kategori_wilayah_data'),
    path('kategori-wilayah/create/', views.KategoriWilayahCreateView.as_view(), name='kategori_wilayah_create'),
    path('kategori-wilayah/<int:pk>/update/', views.KategoriWilayahUpdateView.as_view(), name='kategori_wilayah_update'),
    path('kategori-wilayah/<int:pk>/delete/', views.KategoriWilayahDeleteView.as_view(), name='kategori_wilayah_delete'),
    # Klasifikasi Tabel URLs
    path('klasifikasi-tabel/', views.KlasifikasiTabelListView.as_view(), name='klasifikasi_tabel_list'),
    path('klasifikasi-tabel/data/', views.klasifikasi_tabel_data, name='klasifikasi_tabel_data'),
    path('klasifikasi-tabel/create/', views.KlasifikasiTabelCreateView.as_view(), name='klasifikasi_tabel_create'),
    path('klasifikasi-tabel/<int:pk>/update/', views.KlasifikasiTabelUpdateView.as_view(), name='klasifikasi_tabel_update'),
    path('klasifikasi-tabel/<int:pk>/delete/', views.KlasifikasiTabelDeleteView.as_view(), name='klasifikasi_tabel_delete'),
    # Periode Pengiriman URLs
    path('periode-pengiriman/', views.PeriodePengirimanListView.as_view(), name='periode_pengiriman_list'),
    path('periode-pengiriman/data/', views.periode_pengiriman_data, name='periode_pengiriman_data'),
    path('periode-pengiriman/create/', views.PeriodePengirimanCreateView.as_view(), name='periode_pengiriman_create'),
    path('periode-pengiriman/<int:pk>/update/', views.PeriodePengirimanUpdateView.as_view(), name='periode_pengiriman_update'),
    path('periode-pengiriman/<int:pk>/delete/', views.PeriodePengirimanDeleteView.as_view(), name='periode_pengiriman_delete'),
    # Jenis Data ILAP URLs
    path('jenis-data-ilap/', views.JenisDataILAPListView.as_view(), name='jenis_data_ilap_list'),
    path('jenis-data-ilap/data/', views.jenis_data_ilap_data, name='jenis_data_ilap_data'),
    path('jenis-data-ilap/create/', views.JenisDataILAPCreateView.as_view(), name='jenis_data_ilap_create'),
    path('jenis-data-ilap/<int:pk>/update/', views.JenisDataILAPUpdateView.as_view(), name='jenis_data_ilap_update'),
    path('jenis-data-ilap/<int:pk>/delete/', views.JenisDataILAPDeleteView.as_view(), name='jenis_data_ilap_delete'),
    # Klasifikasi Jenis Data URLs
    path('klasifikasi-jenis-data/', views.KlasifikasiJenisDataListView.as_view(), name='klasifikasi_jenis_data_list'),
    path('klasifikasi-jenis-data/data/', views.klasifikasi_jenis_data_data, name='klasifikasi_jenis_data_data'),
    path('klasifikasi-jenis-data/create/', views.KlasifikasiJenisDataCreateView.as_view(), name='klasifikasi_jenis_data_create'),
    path('klasifikasi-jenis-data/<int:pk>/update/', views.KlasifikasiJenisDataUpdateView.as_view(), name='klasifikasi_jenis_data_update'),
    path('klasifikasi-jenis-data/<int:pk>/delete/', views.KlasifikasiJenisDataDeleteView.as_view(), name='klasifikasi_jenis_data_delete'),
    # Periode Jenis Data URLs
    path('periode-jenis-data/', views.PeriodeJenisDataListView.as_view(), name='periode_jenis_data_list'),
    path('periode-jenis-data/data/', views.periode_jenis_data_data, name='periode_jenis_data_data'),
    path('periode-jenis-data/create/', views.PeriodeJenisDataCreateView.as_view(), name='periode_jenis_data_create'),
    path('periode-jenis-data/<int:pk>/update/', views.PeriodeJenisDataUpdateView.as_view(), name='periode_jenis_data_update'),
    path('periode-jenis-data/<int:pk>/delete/', views.PeriodeJenisDataDeleteView.as_view(), name='periode_jenis_data_delete'),
    # Jenis Prioritas Data URLs
    path('jenis-prioritas-data/', JenisPrioritasDataListView.as_view(), name='jenis_prioritas_data_list'),
    path('jenis-prioritas-data/data/', views.jenis_prioritas_data_data, name='jenis_prioritas_data_data'),
    path('jenis-prioritas-data/create/', views.JenisPrioritasDataCreateView.as_view(), name='jenis_prioritas_data_create'),
    path('jenis-prioritas-data/<int:pk>/update/', views.JenisPrioritasDataUpdateView.as_view(), name='jenis_prioritas_data_update'),
    path('jenis-prioritas-data/<int:pk>/delete/', views.JenisPrioritasDataDeleteView.as_view(), name='jenis_prioritas_data_delete'),
    # Notification URLs
]


    # PIC P3DE URLs
    path('pic-p3de/', views.PICP3DEListView.as_view(), name='pic_p3de_list'),
    path('pic-p3de/data/', views.pic_p3de_data, name='pic_p3de_data'),
    path('pic-p3de/create/', views.PICP3DECreateView.as_view(), name='pic_p3de_create'),
    path('pic-p3de/<int:pk>/update/', views.PICP3DEUpdateView.as_view(), name='pic_p3de_update'),
    path('pic-p3de/<int:pk>/delete/', views.PICP3DEDeleteView.as_view(), name='pic_p3de_delete'),

    # === PIDE Section ===
    # Nama Tabel URLs
    path('nama-tabel/', views.NamaTabelListView.as_view(), name='nama_tabel_list'),
    path('nama-tabel/data/', views.nama_tabel_data, name='nama_tabel_data'),
    path('nama-tabel/create/', views.NamaTabelCreateView.as_view(), name='nama_tabel_create'),
    path('nama-tabel/<int:pk>/update/', views.NamaTabelUpdateView.as_view(), name='nama_tabel_update'),
    path('nama-tabel/<int:pk>/delete/', views.NamaTabelDeleteView.as_view(), name='nama_tabel_delete'),
    # PIC PIDE URLs
    path('pic-pide/', views.PICPIDEListView.as_view(), name='pic_pide_list'),
    path('pic-pide/data/', views.pic_pide_data, name='pic_pide_data'),
    path('pic-pide/create/', views.PICPIDECreateView.as_view(), name='pic_pide_create'),
    path('pic-pide/<int:pk>/update/', views.PICPIDEUpdateView.as_view(), name='pic_pide_update'),
    path('pic-pide/<int:pk>/delete/', views.PICPIDEDeleteView.as_view(), name='pic_pide_delete'),
    # Durasi Jatuh Tempo PIDE URLs
    path('durasi-jatuh-tempo-pide/', views.DurasiJatuhTempoPIDEListView.as_view(), name='durasi_jatuh_tempo_pide_list'),
    path('durasi-jatuh-tempo-pide/data/', views.durasi_jatuh_tempo_pide_data, name='durasi_jatuh_tempo_pide_data'),
    path('durasi-jatuh-tempo-pide/create/', views.DurasiJatuhTempoPIDECreateView.as_view(), name='durasi_jatuh_tempo_pide_create'),
    path('durasi-jatuh-tempo-pide/<int:pk>/update/', views.DurasiJatuhTempoPIDEUpdateView.as_view(), name='durasi_jatuh_tempo_pide_update'),
    path('durasi-jatuh-tempo-pide/<int:pk>/delete/', views.DurasiJatuhTempoPIDEDeleteView.as_view(), name='durasi_jatuh_tempo_pide_delete'),

    # === PMDE Section ===
    # PIC PMDE URLs
    path('pic-pmde/', views.PICPMDEListView.as_view(), name='pic_pmde_list'),
    path('pic-pmde/data/', views.pic_pmde_data, name='pic_pmde_data'),
    path('pic-pmde/create/', views.PICPMDECreateView.as_view(), name='pic_pmde_create'),
    path('pic-pmde/<int:pk>/update/', views.PICPMDEUpdateView.as_view(), name='pic_pmde_update'),
    path('pic-pmde/<int:pk>/delete/', views.PICPMDEDeleteView.as_view(), name='pic_pmde_delete'),

    # Durasi Jatuh Tempo PMDE URLs
    path('durasi-jatuh-tempo-pmde/', views.DurasiJatuhTempoPMDEListView.as_view(), name='durasi_jatuh_tempo_pmde_list'),
    path('durasi-jatuh-tempo-pmde/data/', views.durasi_jatuh_tempo_pmde_data, name='durasi_jatuh_tempo_pmde_data'),
    path('durasi-jatuh-tempo-pmde/create/', views.DurasiJatuhTempoPMDECreateView.as_view(), name='durasi_jatuh_tempo_pmde_create'),
    path('durasi-jatuh-tempo-pmde/<int:pk>/update/', views.DurasiJatuhTempoPMDEUpdateView.as_view(), name='durasi_jatuh_tempo_pmde_update'),
    path('durasi-jatuh-tempo-pmde/<int:pk>/delete/', views.DurasiJatuhTempoPMDEDeleteView.as_view(), name='durasi_jatuh_tempo_pmde_delete'),
]
