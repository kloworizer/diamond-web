from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views.general import keep_alive, session_expired

import sys
print("--- Loading diamond_web/urls.py ---", file=sys.stderr)

urlpatterns = [
    # === Authentication URLs ===
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    path('tanda-terima-data/<int:pk>/view/', views.TandaTerimaDataViewOnly.as_view(), name='tanda_terima_data_view'),
    path('', views.home, name='home'),
    path('home/data/', views.home_data, name='home_data'),
        path('docs/', views.docs_index, name='docs_index'),
    path('docs/<slug:slug>/', views.docs_detail, name='docs_detail'),
    path('keep-alive/', keep_alive, name='keep_alive'),
    path('session-expired/', session_expired, name='session_expired'),
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('profil/', views.ProfilView.as_view(), name='user_profil'),
    path('sync-data-referensi/', views.oracle_sync_page, name='oracle_sync_page'),
    path('sync-data-referensi/test/', views.oracle_sync_test_connection, name='oracle_sync_test'),
    path('sync-data-referensi/check/', views.oracle_sync_check, name='oracle_sync_check'),
    path('sync-data-referensi/run/', views.oracle_sync_run, name='oracle_sync_run'),
    path('sync-data-referensi/stop/', views.oracle_sync_stop, name='oracle_sync_stop'),
    path('sync-data-referensi/clear-session/', views.oracle_sync_clear_session, name='oracle_sync_clear_session'),
    path('sync-data-referensi/progress/', views.oracle_sync_progress, name='oracle_sync_progress'),
    path('sync-data-referensi/truncate/', views.oracle_sync_truncate, name='oracle_sync_truncate'),
    path('sync-data-referensi/download-errors/<str:sync_id>/', views.oracle_sync_download_errors, name='oracle_sync_download_errors'),
    path('sync-data-referensi/stop-check/', views.oracle_sync_stop_check, name='oracle_sync_stop_check'),
    
    path('sync-tiket/', views.sync_tiket_page, name='sync_tiket_page'),
    path('sync-tiket/test/', views.sync_tiket_test_connection, name='sync_tiket_test'),
    path('sync-tiket/check/', views.sync_tiket_check, name='sync_tiket_check'),
    path('sync-tiket/run/', views.sync_tiket_run, name='sync_tiket_run'),
    path('sync-tiket/stop/', views.sync_tiket_stop, name='sync_tiket_stop'),
    path('sync-tiket/stop-check/', views.sync_tiket_stop_check, name='sync_tiket_stop_check'),
    path('sync-tiket/progress/', views.sync_tiket_progress, name='sync_tiket_progress'),
    path('sync-tiket/truncate/', views.sync_tiket_truncate, name='sync_tiket_truncate'),
    path('sync-tiket/download-errors/<str:sync_id>/', views.sync_tiket_download_errors, name='sync_tiket_download_errors'),

    # Sync Log Status
    path('sync-log-status/', views.sync_log_status, name='sync_log_status'),
    path('sync-log-status/download/<str:filename>/', views.sync_log_download, name='sync_log_download'),

    # === Dashboard Section ===
    path('dashboard/', views.DashboardMonitoringView.as_view(), name='dashboard_monitoring'),
    # path('dashboard/', views.index, name='dashboard_index'),

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
    # Profil ILAP URLs
    path('profil-ilap/', views.ProfilILAPListView.as_view(), name='profil_ilap_list'),
    path('profil-ilap/<int:pk>/', views.ProfilILAPDetailView.as_view(), name='profil_ilap_detail'),
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
    # Kanwil URLs
    path('kanwil/', views.KanwilListView.as_view(), name='kanwil_list'),
    path('kanwil/data/', views.kanwil_data, name='kanwil_data'),
    path('kanwil/create/', views.KanwilCreateView.as_view(), name='kanwil_create'),
    path('kanwil/<int:pk>/update/', views.KanwilUpdateView.as_view(), name='kanwil_update'),
    path('kanwil/<int:pk>/delete/', views.KanwilDeleteView.as_view(), name='kanwil_delete'),
    # KPP URLs
    path('kpp/', views.KPPListView.as_view(), name='kpp_list'),
    path('kpp/data/', views.kpp_data, name='kpp_data'),
    path('kpp/create/', views.KPPCreateView.as_view(), name='kpp_create'),
    path('kpp/<int:pk>/update/', views.KPPUpdateView.as_view(), name='kpp_update'),
    path('kpp/<int:pk>/delete/', views.KPPDeleteView.as_view(), name='kpp_delete'),
    # Status Data URLs
    path('status-data/', views.StatusDataListView.as_view(), name='status_data_list'),
    path('status-data/data/', views.status_data_data, name='status_data_data'),
    path('status-data/create/', views.StatusDataCreateView.as_view(), name='status_data_create'),
    path('status-data/<int:pk>/update/', views.StatusDataUpdateView.as_view(), name='status_data_update'),
    path('status-data/<int:pk>/delete/', views.StatusDataDeleteView.as_view(), name='status_data_delete'),
    # Status Penelitian URLs
    path('status-penelitian/', views.StatusPenelitianListView.as_view(), name='status_penelitian_list'),
    path('status-penelitian/data/', views.status_penelitian_data, name='status_penelitian_data'),
    path('status-penelitian/create/', views.StatusPenelitianCreateView.as_view(), name='status_penelitian_create'),
    path('status-penelitian/<int:pk>/update/', views.StatusPenelitianUpdateView.as_view(), name='status_penelitian_update'),
    path('status-penelitian/<int:pk>/delete/', views.StatusPenelitianDeleteView.as_view(), name='status_penelitian_delete'),
    # Dasar Hukum URLs
    path('dasar-hukum/', views.DasarHukumListView.as_view(), name='dasar_hukum_list'),
    path('dasar-hukum/data/', views.dasar_hukum_data, name='dasar_hukum_data'),
    path('dasar-hukum/create/', views.DasarHukumCreateView.as_view(), name='dasar_hukum_create'),
    path('dasar-hukum/<int:pk>/update/', views.DasarHukumUpdateView.as_view(), name='dasar_hukum_update'),
    path('dasar-hukum/<int:pk>/delete/', views.DasarHukumDeleteView.as_view(), name='dasar_hukum_delete'),
    # Periode Pengiriman URLs
    path('periode-pengiriman/', views.PeriodePengirimanListView.as_view(), name='periode_pengiriman_list'),
    path('periode-pengiriman/data/', views.periode_pengiriman_data, name='periode_pengiriman_data'),
    path('periode-pengiriman/create/', views.PeriodePengirimanCreateView.as_view(), name='periode_pengiriman_create'),
    path('periode-pengiriman/<int:pk>/update/', views.PeriodePengirimanUpdateView.as_view(), name='periode_pengiriman_update'),
    path('periode-pengiriman/<int:pk>/delete/', views.PeriodePengirimanDeleteView.as_view(), name='periode_pengiriman_delete'),
    # Bentuk Data URLs
    path('bentuk-data/', views.BentukDataListView.as_view(), name='bentuk_data_list'),
    path('bentuk-data/data/', views.bentuk_data_data, name='bentuk_data_data'),
    path('bentuk-data/create/', views.BentukDataCreateView.as_view(), name='bentuk_data_create'),
    path('bentuk-data/<int:pk>/update/', views.BentukDataUpdateView.as_view(), name='bentuk_data_update'),
    path('bentuk-data/<int:pk>/delete/', views.BentukDataDeleteView.as_view(), name='bentuk_data_delete'),
    # Cara Penyampaian URLs
    path('cara-penyampaian/', views.CaraPenyampaianListView.as_view(), name='cara_penyampaian_list'),
    path('cara-penyampaian/data/', views.cara_penyampaian_data, name='cara_penyampaian_data'),
    path('cara-penyampaian/create/', views.CaraPenyampaianCreateView.as_view(), name='cara_penyampaian_create'),
    path('cara-penyampaian/<int:pk>/update/', views.CaraPenyampaianUpdateView.as_view(), name='cara_penyampaian_update'),
    path('cara-penyampaian/<int:pk>/delete/', views.CaraPenyampaianDeleteView.as_view(), name='cara_penyampaian_delete'),
    # Media Backup URLs
    path('media-backup/', views.MediaBackupListView.as_view(), name='media_backup_list'),
    path('media-backup/data/', views.media_backup_data, name='media_backup_data'),
    path('media-backup/create/', views.MediaBackupCreateView.as_view(), name='media_backup_create'),
    path('media-backup/<int:pk>/update/', views.MediaBackupUpdateView.as_view(), name='media_backup_update'),
    path('media-backup/<int:pk>/delete/', views.MediaBackupDeleteView.as_view(), name='media_backup_delete'),
    # Jenis Data ILAP URLs
    path('jenis-data-ilap/', views.JenisDataILAPListView.as_view(), name='jenis_data_ilap_list'),
    path('jenis-data-ilap/data/', views.jenis_data_ilap_data, name='jenis_data_ilap_data'),
    path('jenis-data/get-next-id/', views.get_next_jenis_data_id, name='get_next_jenis_data_id'),
    path('jenis-data/existing/', views.get_existing_jenis_data, name='get_existing_jenis_data'),
    path('jenis-data/sub/existing/', views.get_existing_sub_jenis_data, name='get_existing_sub_jenis_data'),
    path('jenis-data/sub/next/', views.get_next_sub_jenis_id, name='get_next_sub_jenis_id'),
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
    path('jenis-prioritas-data/', views.JenisPrioritasDataListView.as_view(), name='jenis_prioritas_data_list'),
    path('jenis-prioritas-data/data/', views.jenis_prioritas_data_data, name='jenis_prioritas_data_data'),
    path('jenis-prioritas-data/create/', views.JenisPrioritasDataCreateView.as_view(), name='jenis_prioritas_data_create'),
    path('jenis-prioritas-data/<int:pk>/update/', views.JenisPrioritasDataUpdateView.as_view(), name='jenis_prioritas_data_update'),
    path('jenis-prioritas-data/<int:pk>/delete/', views.JenisPrioritasDataDeleteView.as_view(), name='jenis_prioritas_data_delete'),
    # PIC P3DE URLs
    path('pic-p3de/', views.PICP3DEListView.as_view(), name='pic_p3de_list'),
    path('pic-p3de/data/', views.pic_p3de_data, name='pic_p3de_data'),
    path('pic-p3de/create/', views.PICP3DECreateView.as_view(), name='pic_p3de_create'),
    path('pic-p3de/<int:pk>/update/', views.PICP3DEUpdateView.as_view(), name='pic_p3de_update'),
    path('pic-p3de/<int:pk>/delete/', views.PICP3DEDeleteView.as_view(), name='pic_p3de_delete'),
    # DOCX Template URLs
    path('docx-template/', views.DocxTemplateListView.as_view(), name='docx_template_list'),
    path('docx-template/data/', views.docx_template_data, name='docx_template_data'),
    path('docx-template/create/', views.DocxTemplateCreateView.as_view(), name='docx_template_create'),
    path('docx-template/<int:pk>/update/', views.DocxTemplateUpdateView.as_view(), name='docx_template_update'),
    path('docx-template/<int:pk>/delete/', views.DocxTemplateDeleteView.as_view(), name='docx_template_delete'),
    path('docx-template/<int:pk>/download/', views.docx_template_download, name='docx_template_download'),
    # Sequence Tanda Terima URLs
    path('sequence-tanda-terima/', views.SequenceTandaTerimaListView.as_view(), name='sequence_tanda_terima_list'),
    path('sequence-tanda-terima/data/', views.sequence_tanda_terima_data, name='sequence_tanda_terima_data'),
    path('sequence-tanda-terima/create/', views.SequenceTandaTerimaCreateView.as_view(), name='sequence_tanda_terima_create'),
    path('sequence-tanda-terima/<int:pk>/update/', views.SequenceTandaTerimaUpdateView.as_view(), name='sequence_tanda_terima_update'),
    path('sequence-tanda-terima/<int:pk>/delete/', views.SequenceTandaTerimaDeleteView.as_view(), name='sequence_tanda_terima_delete'),
    # Register Penerimaan Data
    path('register-penerimaan-data/', views.LaporanRegisterPenerimaanView.as_view(), name='register_penerimaan_data'),
    path('register-penerimaan-data/data/', views.register_penerimaan_data, name='register_penerimaan_data_data'),
    path('register-penerimaan-data/export/', views.register_penerimaan_export, name='register_penerimaan_export'),
    # Bulk Document Generation (P3DE)
    path('bulk-generate/pkdi-klarifikasi/', views.bulk_pkdi_klarifikasi, name='bulk_pkdi_klarifikasi'),
    path('bulk-generate/nd-pengantar-pide/', views.bulk_nd_pengantar_pide, name='bulk_nd_pengantar_pide'),
    # Tanda Terima Data URLs
    path('tanda-terima-data/', views.TandaTerimaDataListView.as_view(), name='tanda_terima_data_list'),
    path('tanda-terima-data/data/', views.tanda_terima_data_data, name='tanda_terima_data_data'),
    path('tanda-terima-data/next-number/', views.tanda_terima_next_number, name='tanda_terima_next_number'),
    path('tanda-terima-data/tikets-by-ilap/', views.tanda_terima_tikets_by_ilap, name='tanda_terima_tikets_by_ilap'),
    path('tanda-terima-data/create/', views.TandaTerimaDataCreateView.as_view(), name='tanda_terima_data_create'),
    path('tanda-terima-data/from-tiket/<int:tiket_pk>/create/', views.TandaTerimaDataFromTiketCreateView.as_view(), name='tanda_terima_data_from_tiket_create'),
    path('tanda-terima-data/from-tiket/<int:pk>/tidak-terbit/', views.tidak_terbit_tanda_terima, name='tidak_terbit_tanda_terima'),
    path('tanda-terima-data/<int:pk>/update/', views.TandaTerimaDataUpdateView.as_view(), name='tanda_terima_data_update'),
    path('tanda-terima-data/<int:pk>/delete/', views.TandaTerimaDataDeleteView.as_view(), name='tanda_terima_data_delete'),
    # Monitoring Penyampaian Data URLs
    path('monitoring-penyampaian-data/', views.MonitoringPenyampaianDataListView.as_view(), name='monitoring_penyampaian_data_list'),
    path('monitoring-penyampaian-data/data/', views.monitoring_penyampaian_data_data, name='monitoring_penyampaian_data_data'),

    # === PIDE Section ===

    # Filter Options URLs for cascading filter in PIDE reports
    path('laporan-pide/filter-options/', views.laporan_pide_filter_options, name='laporan_pide_filter_options'),

    # Laporan Transfer
    path('laporan-transfer/', views.LaporanTransferView.as_view(), name='laporan_transfer'),
    path('laporan-transfer/data/', views.laporan_transfer_data, name='laporan_transfer_data'),
    path('laporan-transfer/export/', views.laporan_transfer_export, name='laporan_transfer_export'),

    # Laporan SLA Perekaman
    path('laporan-sla-perekaman/', views.LaporanSLAPerekamanView.as_view(), name='laporan_sla_perekaman'),
    path('laporan-sla-perekaman/data/', views.laporan_sla_perekaman_data, name='laporan_sla_perekaman_data'),
    path('laporan-sla-perekaman/export/', views.laporan_sla_perekaman_export, name='laporan_sla_perekaman_export'),
    
    # Laporan SLA Identifikasi
    path('laporan-sla-identifikasi/', views.LaporanSLAIdentifikasiView.as_view(), name='laporan_sla_identifikasi'),
    path('laporan-sla-identifikasi/data/', views.laporan_sla_identifikasi_data, name='laporan_sla_identifikasi_data'),
    path('laporan-sla-identifikasi/export/', views.laporan_sla_identifikasi_export, name='laporan_sla_identifikasi_export'),

    # Laporan Metrik Data Eksternal
    path('laporan-metrik-data-eksternal/', views.LaporanMetrikDataEksternalView.as_view(), name='laporan_metrik_data_eksternal'),
    path('laporan-metrik-data-eksternal/data/', views.laporan_metrik_data_eksternal_data, name='laporan_metrik_data_eksternal_data'),
    path('laporan-metrik-data-eksternal/export/', views.laporan_metrik_data_eksternal_export, name='laporan_metrik_data_eksternal_export'),

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

    # Laporan Pengendalian Mutu
    path('laporan-pengendalian-mutu/', views.LaporanPengendalianMutuView.as_view(), name='laporan_pengendalian_mutu'),
    path('laporan-pengendalian-mutu/data/', views.laporan_pengendalian_mutu_data, name='laporan_pengendalian_mutu_data'),
    path('laporan-pengendalian-mutu/export/', views.laporan_pengendalian_mutu_export, name='laporan_pengendalian_mutu_export'),
    # Laporan Hasil Pengolahan Data Prioritas
    path('laporan-hasil-pengolahan-data-prioritas/', views.LaporanHasilPengolahanDataPrioritasView.as_view(), name='laporan_hasil_pengolahan_data_prioritas'),
    path('laporan-hasil-pengolahan-data-prioritas/data/', views.laporan_hasil_pengolahan_data_prioritas_data, name='laporan_hasil_pengolahan_data_prioritas_data'),
    path('laporan-hasil-pengolahan-data-prioritas/export/', views.laporan_hasil_pengolahan_data_prioritas_export, name='laporan_hasil_pengolahan_data_prioritas_export'),
    # === PMDE Section ===
    # Laporan Kelengkapan Data
    path('laporan-kelengkapan-data/', views.LaporanKelengkapanDataView.as_view(), name='laporan_kelengkapan_data'),
    path('laporan-kelengkapan-data/data/', views.laporan_kelengkapan_data_data, name='laporan_kelengkapan_data_data'),
    path('laporan-kelengkapan-data/export/', views.laporan_kelengkapan_data_export, name='laporan_kelengkapan_data_export'),
    # Laporan Rekap Penghimpunan dan Pengolahan Data
    path('laporan-rekap-himpun-olah-data/', views.LaporanRekapHimpunOlahDataView.as_view(), name='laporan_rekap_himpun_olah_data'),
    path('laporan-rekap-himpun-olah-data/data/', views.laporan_rekap_himpun_olah_data_data, name='laporan_rekap_himpun_olah_data_data'),
    path('laporan-rekap-himpun-olah-data/export/', views.laporan_rekap_himpun_olah_data_export, name='laporan_rekap_himpun_olah_data_export'),
    # Laporan Detail Penghimpunan dan Pengolahan Data
    path('laporan-detail-himpun-olah-data/', views.LaporanDetailHimpunOlahDataView.as_view(), name='laporan_detail_himpun_olah_data'),
    path('laporan-detail-himpun-olah-data/data/', views.laporan_detail_himpun_olah_data_data, name='laporan_detail_himpun_olah_data_data'),
    path('laporan-detail-himpun-olah-data/export/', views.laporan_detail_himpun_olah_data_export, name='laporan_detail_himpun_olah_data_export'),
    # Quality Control URLs
    path('quality-control/', views.QualityControlView.as_view(), name='quality_control'),
    path('quality-control/data/', views.quality_control_data, name='quality_control_data'),
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

    # Backup Data URLs
    path('backup-data/', views.BackupDataListView.as_view(), name='backup_data_list'),
    path('backup-data/data/', views.backup_data_data, name='backup_data_data'),
    path('backup-data/filter-options/', views.backup_data_filter_options, name='backup_data_filter_options'),
    path('backup-data/export/excel/', views.backup_data_export_excel, name='backup_data_export_excel'),
    path('backup-data/export/pdf/', views.backup_data_export_pdf, name='backup_data_export_pdf'),
    path('backup-data/create/', views.BackupDataCreateView.as_view(), name='backup_data_create'),
    path('backup-data/from-tiket/<int:tiket_pk>/create/', views.BackupDataFromTiketCreateView.as_view(), name='backup_data_from_tiket_create'),
    path('backup-data/<int:pk>/update/', views.BackupDataUpdateView.as_view(), name='backup_data_update'),
    path('backup-data/<int:pk>/delete/', views.BackupDataDeleteView.as_view(), name='backup_data_delete'),
    # === Tiket Workflow ===
    # List view (shared across all workflow steps)
    path('tiket/', views.TiketListView.as_view(), name='tiket_list'),
    path('tiket/data/', views.tiket_data, name='tiket_data'),
    path('tiket/<int:pk>/documents/download/', views.tiket_documents_download, name='tiket_documents_download'),
    # Tiket Identifikasi URLs
    path('tiket/identifikasi/', views.TiketListView.as_view(), name='tiket_identifikasi_list'),
    path('tiket/identifikasi/create/', views.TiketRekamCreateView.as_view(), name='tiket_identifikasi_create'),
    path('tiket/identifikasi/<int:pk>/update/', views.IdentifikasiTiketView.as_view(), name='tiket_identifikasi_update'),
    # Tiket Kirim URLs
    path('tiket/kirim/', views.TiketListView.as_view(), name='tiket_kirim_list'),
    path('tiket/kirim/<int:pk>/update/', views.KirimTiketView.as_view(), name='tiket_kirim_update'),
    
    # API endpoints
    path('api/ilap/<int:ilap_id>/periode-jenis-data/', views.ILAPPeriodeDataAPIView.as_view(), name='api_ilap_periode_jenis_data'),
    path('api/check-jenis-prioritas/<str:jenis_data_id>/<int:tahun>/', views.CheckJenisPrioritasAPIView.as_view(), name='check_jenis_prioritas'),
    path('api/check-tiket-exists/', views.CheckTiketExistsAPIView.as_view(), name='check_tiket_exists'),
    path('api/preview-nomor-tiket/', views.PreviewNomorTiketAPIView.as_view(), name='preview_nomor_tiket'),
    
    # Legacy URLs - kept for backward compatibility
    path('tiket/create/', views.TiketRekamCreateView.as_view(), name='tiket_create'),
    path('tiket/<int:pk>/', views.TiketDetailView.as_view(), name='tiket_detail'),
    
    # Rekam (Record) Workflow Step - Step 1
    path('tiket/rekam/', views.TiketRekamCreateView.as_view(), name='tiket_rekam_create'),
    
    # Kirim Tiket (Send Tiket) - Step 3
    path('tiket/kirim-tiket/', views.KirimTiketView.as_view(), name='kirim_tiket'),
    path('tiket/<int:tiket_pk>/kirim-pide/', views.KirimTiketView.as_view(), name='kirim_tiket_from_tiket'),
    path('tiket/kirim-tiket/download/<int:id_temp>/', views.DownloadNDPengantarView.as_view(), name='kirim_tiket_download'),
    path('tiket/kirim-tiket/temp-update/<int:id_temp>/', views.KirimPideTempUpdateView.as_view(), name='kirim_tiket_temp_update'),
    path('tiket/kirim-tiket/temp-delete/<int:id_temp>/', views.KirimPideTempDeleteView.as_view(), name='kirim_tiket_temp_delete'),
    path('tiket/kirim-tiket/kirim-ke-pide/<int:id_temp>/', views.KirimKePIDEView.as_view(), name='kirim_ke_pide'),
    
    # PIDE and PMDE Workflow Actions (Modal-only forms in tiket detail page)
    # - Batalkan Tiket (Cancel Tiket): batalkan_tiket endpoint for AJAX modal
    # - Rekam Hasil Penelitian: rekam_hasil_penelitian endpoint for AJAX modal
    # - Dikembalikan Tiket: dikembalikan_tiket endpoint for AJAX modal
    # - Identifikasi Tiket: identifikasi_tiket endpoint for AJAX modal
    # - Transfer ke PMDE: transfer_ke_pmde endpoint for AJAX modal
    # - Selesaikan Tiket: selesaikan_tiket endpoint for AJAX modal
    path('tiket/<int:pk>/batalkan/', views.BatalkanTiketView.as_view(), name='batalkan_tiket'),
    path('tiket/<int:pk>/rekam-hasil-penelitian/', views.RekamHasilPenelitianView.as_view(), name='rekam_hasil_penelitian'),
    path('tiket/<int:pk>/dikembalikan/', views.DikembalikanTiketView.as_view(), name='dikembalikan_tiket'),
    path('tiket/<int:pk>/identifikasi/', views.IdentifikasiTiketView.as_view(), name='identifikasi_tiket'),
    path('tiket/<int:pk>/transfer-ke-pmde/', views.TransferKePMDEView.as_view(), name='transfer_ke_pmde'),
    path('tiket/<int:pk>/selesaikan/', views.SelesaikanTiketView.as_view(), name='selesaikan_tiket'),

]
