from django.contrib import admin
from .models import UserProfile, PerbaikanJasa, PembelianCabang, ItemPembelianCabang

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'nik', 'role', 'divisi')
    list_filter = ('role', 'divisi')
    search_fields = ('user__username', 'nik', 'user__first_name', 'user__last_name')

@admin.register(PerbaikanJasa)
class PerbaikanJasaAdmin(admin.ModelAdmin):
    list_display = ('id', 'objek', 'divisi', 'status', 'urgensi', 'progress_pekerjaan', 'tanggal')
    list_filter = ('status', 'urgensi', 'progress_pekerjaan', 'divisi')
    search_fields = ('objek', 'nama', 'nik')


# Menampilkan list barang langsung di dalam halaman detail PembelianCabang
class ItemPembelianCabangInline(admin.TabularInline):
    model = ItemPembelianCabang
    extra = 1


@admin.register(PembelianCabang)
class PembelianCabangAdmin(admin.ModelAdmin):
    # 'nama_barang' diganti dengan ringkasan jumlah item dan total estimasi harga
    list_display = ('id', 'nama', 'nik', 'display_total_item', 'display_total_estimasi', 'status_approval', 'tahapan_ga', 'tanggal')
    list_filter = ('status_approval', 'tahapan_ga', 'tanggal')
    search_fields = ('nama', 'nik')
    inlines = [ItemPembelianCabangInline]

    @admin.display(description='Jumlah Barang')
    def display_total_item(self, obj):
        return f"{obj.total_item} Item"

    @admin.display(description='Total Estimasi (Rp)')
    def display_total_estimasi(self, obj):
        return f"Rp {obj.total_estimasi:,.0f}"


@admin.register(ItemPembelianCabang)
class ItemPembelianCabangAdmin(admin.ModelAdmin):
    list_display = ('id', 'pembelian', 'nama_barang', 'estimasi_harga')
    search_fields = ('nama_barang', 'pembelian__nama', 'pembelian__nik')