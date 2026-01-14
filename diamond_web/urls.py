from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('notifications/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
]