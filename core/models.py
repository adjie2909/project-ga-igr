from django.db import models
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
from io import BytesIO
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from django.core.files.base import ContentFile

# --- PROFILE USER DENGAN ROLE & DIVISI ---
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('USER', 'User Divisi'),
        ('GA', 'General Affair (GA)'),
        ('SAM', 'SAM'),
        ('SM', 'Store Manager (SM)'),
        ('TEKNISI', 'Teknisi'),
    ]
    
    DIVISI_CHOICES = [
        ('SM', 'SM'),
        ('BO', 'BO'),
        ('MS', 'MS'),
        ('FOOD', 'FOOD'),
        ('NON FOOD', 'NON FOOD'),
        ('PERISH', 'PERISH'),
        ('LOG 1', 'LOG 1'),
        ('LOG 2', 'LOG 2'),
        ('GA', 'GA'),
        ('TEKNISI', 'TEKNISI'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    nik = models.CharField(max_length=30, blank=True)
    nomor_hp = models.CharField(max_length=20, blank=True, null=True, verbose_name="Nomor HP/WhatsApp")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='USER')
    divisi = models.CharField(max_length=20, choices=DIVISI_CHOICES, default='BO')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.role} ({self.divisi})"


# --- MODUL 1: PERBAIKAN DAN JASA ---
class PerbaikanJasa(models.Model):
    URGENSI_CHOICES = [
        ('EMERGENCY', 'Emergency'),
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('PLANNED', 'Planned'),
    ]

    STATUS_APPROVAL_CHOICES = [
        ('WAITING_GA', 'Menunggu Estimasi GA'),
        ('WAITING_SAM', 'Menunggu Review SAM'),
        ('APPROVED', 'Disetujui (Diteruskan ke Teknisi)'),
        ('REJECTED', 'Ditolak (NOK)'),
    ]

    PROGRESS_TEKNISI_CHOICES = [
        ('BELUM DIKERJAKAN', 'Belum Dikerjakan'),
        ('PROSES', 'Proses'),
        ('SELESAI', 'Selesai'),
    ]
    # field no_dokumen
    no_dokumen = models.CharField(max_length=50, unique=True, blank=True, null=True)
    # Input User
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='perbaikan_requests')
    nik = models.CharField(max_length=50)
    nama = models.CharField(max_length=150)
    divisi = models.CharField(max_length=50)
    tanggal = models.DateField(auto_now_add=True)
    lokasi_spesifik = models.CharField(max_length=255)
    objek = models.CharField(max_length=255)
    detail = models.TextField()
    upload_foto = models.ImageField(upload_to='perbaikan/laporan/')

    # Input GA
    deskripsi_kebutuhan_bahan = models.TextField(blank=True, null=True)
    estimasi_harga = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Review SAM
    urgensi = models.CharField(max_length=20, choices=URGENSI_CHOICES, blank=True, null=True)
    alasan_nok_sam = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_APPROVAL_CHOICES, default='WAITING_GA')

    # Progress Teknisi
    progress_pekerjaan = models.CharField(
        max_length=30, choices=PROGRESS_TEKNISI_CHOICES, default='BELUM DIKERJAKAN'
    )
    kendala = models.TextField(blank=True, null=True)
    foto_hasil_pekerjaan = models.ImageField(upload_to='perbaikan/selesai/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def target_deadline(self):
        """Menghitung batas akhir SLA berdasarkan tanggal dibuat dan urgensi"""
        if not self.urgensi:
            return None
        durations = {
            'EMERGENCY': timedelta(days=1),
            'HIGH': timedelta(days=2),
            'MEDIUM': timedelta(days=5),
            'PLANNED': timedelta(days=14),
        }
        return self.created_at + durations.get(self.urgensi, timedelta(days=7))

    @property
    def is_overdue(self):
        """Mengecek apakah tiket sudah melewati deadline jika belum selesai"""
        if self.progress_pekerjaan == 'SELESAI' or not self.target_deadline:
            return False
        return timezone.now() > self.target_deadline

    @property
    def remaining_hours(self):
        """Menghitung sisa jam sebelum batas SLA"""
        if not self.target_deadline or self.progress_pekerjaan == 'SELESAI':
            return None
        delta = self.target_deadline - timezone.now()
        return round(delta.total_seconds() / 3600, 1)

    def save(self, *args, **kwargs):
        # 1. Kompres foto laporan awal
        if self.upload_foto:
            img = Image.open(self.upload_foto)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            max_size = (1600, 1600)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            output = BytesIO()
            img.save(output, format='JPEG', quality=75, optimize=True)
            output.seek(0)
            self.upload_foto = ContentFile(output.read(), name=self.upload_foto.name)

        # 2. Kompres foto hasil teknisi
        if self.foto_hasil_pekerjaan:
            try:
                if hasattr(self.foto_hasil_pekerjaan.file, 'read'):
                    self.foto_hasil_pekerjaan = compress_image(self.foto_hasil_pekerjaan)
            except Exception:
                pass

        # 3. Generate nomor dokumen PJ otomatis
        if not self.no_dokumen:
            self.no_dokumen = generate_document_number(PerbaikanJasa, 'PJ')

        # 4. Simpan ke database (cukup 1 kali)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.get_status_display()}] {self.objek} - {self.divisi}"


# --- MODUL 2: PEMBELIAN CABANG ---
class PembelianCabang(models.Model):
    STATUS_APPROVAL_CHOICES = [
        ('WAITING_SAM', 'Menunggu Approval SAM'),
        ('WAITING_SM', 'Menunggu Approval SM'),
        ('APPROVED_TO_GA', 'Disetujui (Diteruskan ke GA)'),
        ('REJECTED_SAM', 'Ditolak SAM (NOK)'),
        ('REJECTED_SM', 'Ditolak SM (NOK)'),
    ]

    TAHAPAN_GA_CHOICES = [
        ('PENDING', 'Pending Belum Diproses'),
        ('SEARCH', 'Dicari Toko / Vendor'),
        ('BOUGHT', 'Dibeli'),
        ('SHIPPED', 'Dikirim'),
        ('ARRIVED', 'Tiba'),
        ('HANDOVER', 'Handover (Selesai/Diserahkan)'),
    ]
    #field no_dokumen
    no_dokumen = models.CharField(max_length=50, unique=True, blank=True, null=True)
    # Header Pengajuan
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pembelian_requests')
    nik = models.CharField(max_length=50)
    nama = models.CharField(max_length=150)
    tanggal = models.DateField(auto_now_add=True)

    # Approval SAM
    keterangan_sam = models.TextField(blank=True, null=True)
    is_approved_sam = models.BooleanField(null=True, blank=True)

    # Approval SM
    keterangan_sm = models.TextField(blank=True, null=True)
    is_approved_sm = models.BooleanField(null=True, blank=True)

    status_approval = models.CharField(
        max_length=30, choices=STATUS_APPROVAL_CHOICES, default='WAITING_SAM'
    )

    # Tracking & Pembelian oleh GA
    tahapan_ga = models.CharField(
        max_length=20, choices=TAHAPAN_GA_CHOICES, default='PENDING'
    )
    nomor_invoice = models.CharField(max_length=100, blank=True, null=True)
    upload_invoice = models.FileField(upload_to='pembelian/invoice/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Generate no_dokumen otomatis untuk Pembelian Cabang
        if not self.no_dokumen:
            self.no_dokumen = generate_document_number(PembelianCabang, 'PB')
        super().save(*args, **kwargs)

    @property
    def total_estimasi(self):
        return sum(item.estimasi_harga for item in self.items.all() if item.estimasi_harga)

    @property
    def total_item(self):
        return self.items.count()

    def __str__(self):
        return f"Pengajuan #{self.id} - {self.nama} ({self.get_status_approval_display()})"


class ItemPembelianCabang(models.Model):
    pembelian = models.ForeignKey(PembelianCabang, on_delete=models.CASCADE, related_name='items')
    nama_barang = models.CharField(max_length=255)
    deskripsi_fungsi_peruntukan = models.TextField()
    estimasi_harga = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    referensi = models.CharField(max_length=255, blank=True, help_text="Link atau info toko")
    upload_foto = models.ImageField(upload_to='pembelian/referensi/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.upload_foto:
            img = Image.open(self.upload_foto)
            # Konversi jika format RGBA/PNG ke RGB
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Batasi dimensi maksimal ke 1600px
            max_size = (1600, 1600)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            output = BytesIO()
            img.save(output, format='JPEG', quality=75, optimize=True)
            output.seek(0)
            
            # Timpa file asli dengan file hasil kompresi
            self.upload_foto = ContentFile(output.read(), name=self.upload_foto.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nama_barang} (Pengajuan #{self.pembelian_id})"

    @property
    def referensi_url(self):
        """Memastikan link referensi selalu memiliki skema http/https agar tidak dianggap relative path."""
        ref = self.referensi.strip() if self.referensi else ""
        if not ref:
            return ""
        if ref.startswith(('http://', 'https://')):
            return ref
        return f"https://{ref}"

    def __str__(self):
        return f"{self.nama_barang} (Pengajuan #{self.pembelian_id})"

def compress_image(image_field, max_width=1280, quality=75):
    """
    Mengompres dan meresize gambar ke batas max_width serta kompresi JPEG quality.
    """
    if not image_field:
        return image_field

    img = Image.open(image_field)
    
    # Konversi RGBA ke RGB jika formatnya PNG transparan agar bisa dikompres JPEG
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    # Resize proporsional jika lebih lebar dari max_width
    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_height = int((float(img.height) * float(ratio)))
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

    output = BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
    output.seek(0)

    # Buat nama file baru berekstensi .jpg
    new_filename = f"{image_field.name.split('.')[0]}.jpg"

    return InMemoryUploadedFile(
        output,
        'ImageField',
        new_filename,
        'image/jpeg',
        sys.getsizeof(output),
        None
    )

# Helper Function Generator Nomor Dokumen (Reset tiap pergantian bulan)
def generate_document_number(model_class, prefix):
    today = timezone.now().date()
    year_str = today.strftime('%Y')
    month_str = today.strftime('%m')
    day_str = today.strftime('%d')
    prefix_filter = f"{prefix}/{year_str}/{month_str}/"

    # Cari nomor dokumen terakhir di tahun dan bulan yang sama
    last_doc = model_class.objects.filter(
        no_dokumen__startswith=prefix_filter
    ).order_by('-no_dokumen').first()

    if last_doc and last_doc.no_dokumen:
        try:
            # Mengambil 4 digit angka paling belakang
            last_seq = int(last_doc.no_dokumen.split('/')[-1])
            new_seq = last_seq + 1
        except (ValueError, IndexError):
            new_seq = 1
    else:
        # Reset ke 1 jika awal bulan baru atau belum ada data di bulan tersebut
        new_seq = 1

    return f"{prefix}/{year_str}/{month_str}/{day_str}/{new_seq:04d}"

