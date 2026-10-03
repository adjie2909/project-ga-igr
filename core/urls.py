from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    
    # Modul 1: Perbaikan & Jasa
    path('perbaikan/', views.perbaikan_list, name='perbaikan_list'),
    path('perbaikan/tambah/', views.perbaikan_create, name='perbaikan_create'),
    path('perbaikan/<path:no_dokumen>/', views.perbaikan_detail, name='perbaikan_detail'),
    path('perbaikan/<path:no_dokumen>/hapus/', views.perbaikan_delete, name='perbaikan_delete'),

    # Modul 2: Pembelian Cabang
    path('pembelian/', views.pembelian_list, name='pembelian_list'),
    path('pembelian/tambah/', views.pembelian_create, name='pembelian_create'),
    path('pembelian/<int:pk>/', views.pembelian_detail, name='pembelian_detail'),
    path('pembelian/<path:no_dokumen>/', views.pembelian_detail, name='pembelian_detail'),
    path('pembelian/<path:no_dokumen>/cetak-handover/', views.pembelian_print_handover, name='pembelian_print_handover'),
    # path('pembelian/<path:no_dokumen>/cetak-handover/', views.cetak_handover, name='cetak_handover'),

    # Fitur Export Khusus GA
    path('export/laporan-excel/', views.export_laporan_excel, name='export_laporan_excel'),
]