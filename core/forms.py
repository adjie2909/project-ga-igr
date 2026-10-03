from django import forms
from django.forms import inlineformset_factory
from django.forms.widgets import ClearableFileInput
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import PerbaikanJasa, PembelianCabang, ItemPembelianCabang, UserProfile


# ==========================================
# 1. FORMS MODUL PERBAIKAN & JASA
# ==========================================

class PerbaikanJasaUserForm(forms.ModelForm):
    class Meta:
        model = PerbaikanJasa
        fields = ['nik', 'nama', 'divisi', 'lokasi_spesifik', 'objek', 'detail', 'upload_foto']
        widgets = {
            'nik': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan NIK'}),
            'nama': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Lengkap'}),
            'divisi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: BO, FOOD, LOG 1'}),
            'lokasi_spesifik': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: Lantai 2 / Area Kasir'}),
            'objek': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contoh: AC Cassette, Forklift, Lampu'}),
            'detail': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Jelaskan kerusakan / kebutuhan jasa...'}),
            'upload_foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class PerbaikanJasaGAForm(forms.ModelForm):
    class Meta:
        model = PerbaikanJasa
        fields = ['deskripsi_kebutuhan_bahan', 'estimasi_harga']
        widgets = {
            'deskripsi_kebutuhan_bahan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Rincian material/jasa pihak ketiga'}),
            'estimasi_harga': forms.TextInput(attrs={'class': 'form-control currency-input'}),
        }

class PerbaikanJasaSAMForm(forms.ModelForm):
    urgensi = forms.ChoiceField(
        choices=[('', '-- Pilih Urgensi --')] + PerbaikanJasa.URGENSI_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    alasan_nok_sam = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Wajib diisi jika ditolak (NOK)'})
    )

    class Meta:
        model = PerbaikanJasa
        fields = ['urgensi', 'alasan_nok_sam']

class PerbaikanJasaTeknisiForm(forms.ModelForm):
    class Meta:
        model = PerbaikanJasa
        fields = ['progress_pekerjaan', 'kendala', 'foto_hasil_pekerjaan']
        widgets = {
            'progress_pekerjaan': forms.Select(attrs={'class': 'form-select'}),
            'kendala': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Catat kendala teknis bila ada'}),
            'foto_hasil_pekerjaan': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


# ==========================================
# 2. FORMS MODUL PEMBELIAN CABANG
# ==========================================

class PembelianCabangHeaderForm(forms.ModelForm):
    class Meta:
        model = PembelianCabang
        fields = ['nik', 'nama']
        widgets = {
            'nik': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan NIK'}),
            'nama': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Lengkap Pemohon'}),
        }

class ItemPembelianCabangForm(forms.ModelForm):
    class Meta:
        model = ItemPembelianCabang
        fields = ['nama_barang', 'deskripsi_fungsi_peruntukan', 'estimasi_harga', 'referensi', 'upload_foto']
        widgets = {
            'nama_barang': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nama Barang / Alat'}),
            'deskripsi_fungsi_peruntukan': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Fungsi & peruntukannya...'}),
            'estimasi_harga': forms.TextInput(attrs={'class': 'form-control currency-input'}),
            'referensi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Link Toko / E-commerce'}),
            'upload_foto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

ItemPembelianFormSet = inlineformset_factory(
    PembelianCabang,
    ItemPembelianCabang,
    form=ItemPembelianCabangForm,
    extra=1,
    can_delete=True
)

class PembelianSAMReviewForm(forms.ModelForm):
    class Meta:
        model = PembelianCabang
        fields = ['keterangan_sam']
        widgets = {
            'keterangan_sam': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Catatan / alasan keputusan SAM'}),
        }

class PembelianSMReviewForm(forms.ModelForm):
    class Meta:
        model = PembelianCabang
        fields = ['keterangan_sm']
        widgets = {
            'keterangan_sm': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Catatan / alasan keputusan SM'}),
        }

# Custom widget untuk teks bahasa Indonesia pada upload invoice
class CustomClearableFileInput(ClearableFileInput):
    initial_text = 'Status file'
    input_text = 'Ganti file'
    clear_checkbox_label = 'Hapus file'
    template_with_initial = (
        '<div class="mb-1 small">'
        '%(initial_text)s: <a href="%(initial_url)s" target="_blank" class="fw-semibold text-primary">Bukti invoice/struk</a> '
        '%(clear_template)s'
        '</div>'
        '<div>%(input_text)s: %(input)s</div>'
    )

class PembelianGATrackingForm(forms.ModelForm):
    class Meta:
        model = PembelianCabang
        fields = ['tahapan_ga', 'nomor_invoice', 'upload_invoice']
        labels = {
            'upload_invoice': 'Bukti Invoice / Struk',
        }
        widgets = {
            'tahapan_ga': forms.Select(attrs={'class': 'form-select'}),
            'nomor_invoice': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nomor invoice / resi (jika ada)'}),
            'upload_invoice': CustomClearableFileInput(attrs={'class': 'form-control'}),  # <-- Menggunakan CustomClearableFileInput
        }


# ==========================================
# 3. FORM REGISTRASI USER
# ==========================================

class RegisterForm(forms.Form):
    user_id = forms.CharField(
        max_length=3,
        min_length=3,
        label="User ID",
        widget=forms.TextInput(attrs={
            'class': 'form-control uppercase-input',
            'maxlength': '3',
            'autocomplete': 'off',
            'style': 'text-transform: uppercase;'
        })
    )
    nama_lengkap = forms.CharField(
        max_length=150,
        label="Nama Lengkap",
        widget=forms.TextInput(attrs={
            'class': 'form-control uppercase-input',
            'style': 'text-transform: uppercase;'
        })
    )
    nik = forms.CharField(
        max_length=30,
        label="NIK",
        widget=forms.TextInput(attrs={
            'class': 'form-control uppercase-input',
            'style': 'text-transform: uppercase;'
        })
    )
    nomor_hp = forms.CharField(
        max_length=20,
        required=False,
        label="Nomor HP / WhatsApp",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'inputmode': 'numeric'
        })
    )
    role = forms.ChoiceField(
        choices=UserProfile.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    divisi = forms.ChoiceField(
        choices=UserProfile.DIVISI_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••'
        })
    )
    confirm_password = forms.CharField(
        label="Konfirmasi Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••'
        })
    )

    def clean_user_id(self):
        uid = self.cleaned_data.get('user_id', '').strip().upper()
        if len(uid) != 3:
            raise ValidationError("User ID wajib terdiri dari tepat 3 karakter.")
        if User.objects.filter(username__iexact=uid).exists():
            raise ValidationError(f"User ID '{uid}' sudah terdaftar. Gunakan 3 karakter lain.")
        return uid

    def clean_nama_lengkap(self):
        return self.cleaned_data.get('nama_lengkap', '').strip().upper()

    def clean_nik(self):
        return self.cleaned_data.get('nik', '').strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('confirm_password')

        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'Konfirmasi password tidak cocok.')

        return cleaned_data