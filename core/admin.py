from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserProfile, PerbaikanJasa, PembelianCabang, ItemPembelianCabang

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


# 1. Konfigurasi Tampilan CustomUser di Django Admin
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'name', 'email', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'name', 'email')
    ordering = ('username',)

    # Sesuaikan fieldset agar tidak mencari first_name / last_name bawaan
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informasi Pribadi', {'fields': ('name', 'email')}),
        ('Hak Akses / Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Waktu', {'fields': ('last_login', 'date_joined')}),
    )

    # Fieldset saat membuat user baru lewat tombol '+ Add User' di Admin
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'name', 'password'),
        }),
    )

# 2. Daftarkan CustomUser ke Admin
admin.site.register(CustomUser, CustomUserAdmin)

# 3. Model lainnya yang sudah terdaftar (sesuaikan jika sudah ada)
# admin.site.register(UserProfile)
# admin.site.register(PerbaikanJasa)
# admin.site.register(PembelianCabang)
# admin.site.register(ItemPembelianCabang)