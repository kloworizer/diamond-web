from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .views.general import keep_alive, session_expired

urlpatterns = [
    path('', views.home, name='home'),
    path('keep-alive/', keep_alive, name='keep_alive'),
    path('session-expired/', session_expired, name='session_expired'),
    path('notifications/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/change_password_form.html', success_url=reverse_lazy('user_password_change_done')), name='user_password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/change_password_done.html'), name='user_password_change_done'),

    # Kategori ILAP URLs
    path('kategori-ilap/', views.KategoriILAPListView.as_view(), name='kategori_ilap_list'),
    path('kategori-ilap/data/', views.kategori_ilap_data, name='kategori_ilap_data'),
    path('kategori-ilap/create/', views.KategoriILAPCreateView.as_view(), name='kategori_ilap_create'),
    path('kategori-ilap/<str:pk>/update/', views.KategoriILAPUpdateView.as_view(), name='kategori_ilap_update'),
    path('kategori-ilap/<str:pk>/delete/', views.KategoriILAPDeleteView.as_view(), name='kategori_ilap_delete'),
    # Klasifikasi Tabel URLs
    path('klasifikasi-tabel/', views.KlasifikasiTabelListView.as_view(), name='klasifikasi_tabel_list'),
    path('klasifikasi-tabel/data/', views.klasifikasi_tabel_data, name='klasifikasi_tabel_data'),
    path('klasifikasi-tabel/create/', views.KlasifikasiTabelCreateView.as_view(), name='klasifikasi_tabel_create'),
    path('klasifikasi-tabel/<int:pk>/update/', views.KlasifikasiTabelUpdateView.as_view(), name='klasifikasi_tabel_update'),
    path('klasifikasi-tabel/<int:pk>/delete/', views.KlasifikasiTabelDeleteView.as_view(), name='klasifikasi_tabel_delete'),
    # Kategori Wilayah URLs
    path('kategori-wilayah/', views.KategoriWilayahListView.as_view(), name='kategori_wilayah_list'),
    path('kategori-wilayah/data/', views.kategori_wilayah_data, name='kategori_wilayah_data'),
    path('kategori-wilayah/create/', views.KategoriWilayahCreateView.as_view(), name='kategori_wilayah_create'),
    path('kategori-wilayah/<int:pk>/update/', views.KategoriWilayahUpdateView.as_view(), name='kategori_wilayah_update'),
    path('kategori-wilayah/<int:pk>/delete/', views.KategoriWilayahDeleteView.as_view(), name='kategori_wilayah_delete'),
    # Jenis Tabel URLs
    path('jenis-tabel/', views.JenisTabelListView.as_view(), name='jenis_tabel_list'),
    path('jenis-tabel/data/', views.jenis_tabel_data, name='jenis_tabel_data'),
    path('jenis-tabel/create/', views.JenisTabelCreateView.as_view(), name='jenis_tabel_create'),
    path('jenis-tabel/<int:pk>/update/', views.JenisTabelUpdateView.as_view(), name='jenis_tabel_update'),
    path('jenis-tabel/<int:pk>/delete/', views.JenisTabelDeleteView.as_view(), name='jenis_tabel_delete'),
    # Periode Pengiriman URLs
    path('periode-pengiriman/', views.PeriodePengirimanListView.as_view(), name='periode_pengiriman_list'),
    path('periode-pengiriman/data/', views.periode_pengiriman_data, name='periode_pengiriman_data'),
    path('periode-pengiriman/create/', views.PeriodePengirimanCreateView.as_view(), name='periode_pengiriman_create'),
    path('periode-pengiriman/<int:pk>/update/', views.PeriodePengirimanUpdateView.as_view(), name='periode_pengiriman_update'),
    path('periode-pengiriman/<int:pk>/delete/', views.PeriodePengirimanDeleteView.as_view(), name='periode_pengiriman_delete'),
    # ILAP URLs
    path('ilap/', views.ILAPListView.as_view(), name='ilap_list'),
    path('ilap/data/', views.ilap_data, name='ilap_data'),
    path('ilap/next-id/', views.get_next_ilap_id, name='get_next_ilap_id'),
    path('ilap/create/', views.ILAPCreateView.as_view(), name='ilap_create'),
    path('ilap/<str:pk>/update/', views.ILAPUpdateView.as_view(), name='ilap_update'),
    path('ilap/<str:pk>/delete/', views.ILAPDeleteView.as_view(), name='ilap_delete'),
    # Jenis Data ILAP URLs
    path('jenis-data-ilap/', views.JenisDataILAPListView.as_view(), name='jenis_data_ilap_list'),
    path('jenis-data-ilap/data/', views.jenis_data_ilap_data, name='jenis_data_ilap_data'),
    path('jenis-data-ilap/create/', views.JenisDataILAPCreateView.as_view(), name='jenis_data_ilap_create'),
    path('jenis-data-ilap/<int:pk>/update/', views.JenisDataILAPUpdateView.as_view(), name='jenis_data_ilap_update'),
    path('jenis-data-ilap/<int:pk>/delete/', views.JenisDataILAPDeleteView.as_view(), name='jenis_data_ilap_delete'),
]