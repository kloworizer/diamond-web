from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('notifications/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/change_password_form.html', success_url=reverse_lazy('user_password_change_done')), name='user_password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/change_password_done.html'), name='user_password_change_done'),

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
]