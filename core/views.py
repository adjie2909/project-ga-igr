from django.db.models import Q
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import PerbaikanJasa, PembelianCabang, ItemPembelianCabang, UserProfile
from django.core.paginator import Paginator
from zoneinfo import ZoneInfo
from datetime import datetime
from django.contrib.auth.models import User
from .forms import (
    PerbaikanJasaUserForm,
    PerbaikanJasaGAForm,
    PerbaikanJasaSAMForm,
    PerbaikanJasaTeknisiForm,
    PembelianCabangHeaderForm,
    ItemPembelianFormSet,
    PembelianSAMReviewForm,
    PembelianSMReviewForm,
    PembelianGATrackingForm,
    RegisterForm
)



def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        # Back-end sanitizer: trim spasi dan paksa huruf besar
        user_id = request.POST.get('user_id', '').strip().upper()
        password = request.POST.get('password', '')

        if len(user_id) != 3:
            messages.error(request, 'User ID harus terdiri dari tepat 3 karakter.')
            return render(request, 'core/login.html', {'last_user_id': user_id})

        user = authenticate(request, username=user_id, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('core:dashboard')
        else:
            messages.error(request, 'User ID atau password salah.')
            return render(request, 'core/login.html', {'last_user_id': user_id})

    return render(request, 'core/login.html')

def logout_view(request):
    logout(request)
    return redirect('core:login')

@login_required
def dashboard_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    # Metrik Modul Perbaikan & Jasa
    total_perbaikan = PerbaikanJasa.objects.count()
    perbaikan_waiting_ga = PerbaikanJasa.objects.filter(status='WAITING_GA').count()
    perbaikan_waiting_sam = PerbaikanJasa.objects.filter(status='WAITING_SAM').count()
    teknisi_proses = PerbaikanJasa.objects.filter(status='APPROVED', progress_pekerjaan__in=['BELUM DIKERJAKAN', 'PROSES']).count()

    # Metrik Modul Pembelian Cabang
    total_pembelian = PembelianCabang.objects.count()
    pembelian_waiting_sam = PembelianCabang.objects.filter(status_approval='WAITING_SAM').count()
    pembelian_waiting_sm = PembelianCabang.objects.filter(status_approval='WAITING_SM').count()
    pembelian_proses_ga = PembelianCabang.objects.filter(
        status_approval='APPROVED_TO_GA'
    ).exclude(tahapan_ga='HANDOVER').count()

    context = {
        'profile': profile,
        'total_perbaikan': total_perbaikan,
        'perbaikan_waiting_ga': perbaikan_waiting_ga,
        'perbaikan_waiting_sam': perbaikan_waiting_sam,
        'teknisi_proses': teknisi_proses,
        
        'total_pembelian': total_pembelian,
        'pembelian_waiting_sam': pembelian_waiting_sam,
        'pembelian_waiting_sm': pembelian_waiting_sm,
        'pembelian_proses_ga': pembelian_proses_ga,
    }
    return render(request, 'core/dashboard.html', context)

# --- ALUR MODUL 1: PERBAIKAN & JASA ---

@login_required
def perbaikan_list(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # 1. Hak Akses Dasar
    if profile.role == 'USER':
        qs = PerbaikanJasa.objects.filter(user=request.user)
    elif profile.role == 'TEKNISI':
        # Teknisi melihat pekerjaan yang sudah di-approve
        qs = PerbaikanJasa.objects.filter(status='APPROVED')
    else:
        qs = PerbaikanJasa.objects.all()

    # 2. Filter & Pencarian
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    urgensi_filter = request.GET.get('urgensi', '').strip()
    tgl_mulai = request.GET.get('tgl_mulai', '').strip()
    tgl_selesai = request.GET.get('tgl_selesai', '').strip()

    if search_query:
        qs = qs.filter(
            Q(no_dokumen__icontains=search_query) |
            Q(objek__icontains=search_query) |
            Q(lokasi_spesifik__icontains=search_query) |
            Q(nama__icontains=search_query) |
            Q(nik__icontains=search_query)
        )

    if status_filter:
        qs = qs.filter(status=status_filter)

    if urgensi_filter:
        qs = qs.filter(urgensi=urgensi_filter)

    if tgl_mulai:
         qs = qs.filter(tanggal__gte=tgl_mulai)
        
    if tgl_selesai:
        qs = qs.filter(tanggal__lte=tgl_selesai)

    qs = qs.order_by('-created_at')
    paginator = Paginator(qs, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/perbaikan_list.html', {
        'items': page_obj,
        'profile': profile,
        'search_query': search_query,
        'status_filter': status_filter,
        'urgensi_filter': urgensi_filter,
        'tgl_mulai': tgl_mulai,
        'tgl_selesai': tgl_selesai,
        'urgensi_choices': PerbaikanJasa.URGENSI_CHOICES,
        'status_choices': PerbaikanJasa.STATUS_APPROVAL_CHOICES,
    })

@login_required
def perbaikan_delete(request, no_dokumen):
    if no_dokumen.isdigit():
        pj = get_object_or_404(PerbaikanJasa, id=no_dokumen)
    else:
        pj = get_object_or_404(PerbaikanJasa, no_dokumen=no_dokumen)

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    doc_key = pj.no_dokumen or str(pj.id)

    # Validasi hanya SAM atau Superuser yang boleh menghapus
    if profile.role != 'SAM' and not request.user.is_superuser:
        messages.error(request, 'Akses ditolak: Hanya SAM yang berhak menghapus tiket perbaikan.')
        return redirect('core:perbaikan_detail', pk=pj.pk)

    if request.method == 'POST':
        pj_id = pj.id
        pj.delete()
        messages.success(request, f'Permintaan perbaikan #{pj_id} berhasil dihapus oleh SAM.')
        return redirect('core:perbaikan_list')

    return redirect('core:perbaikan_detail', no_dokumen=doc_key)

@login_required
def perbaikan_create(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = PerbaikanJasaUserForm(request.POST, request.FILES)
        if form.is_valid():
            pj = form.save(commit=False)
            pj.user = request.user
            pj.status = 'WAITING_GA'
            pj.save()
            messages.success(request, 'Permintaan perbaikan berhasil dikirim ke GA.')
            return redirect('core:perbaikan_list')
    else:
        # Pre-fill NIK & Divisi dari profil jika ada
        form = PerbaikanJasaUserForm(initial={
            'nik': profile.nik,
            'nama': request.user.get_full_name() or request.user.username,
            'divisi': profile.divisi
        })
    return render(request, 'core/perbaikan_create.html', {'form': form})

@login_required
def perbaikan_detail(request, no_dokumen):
    if no_dokumen.isdigit():
        pj = get_object_or_404(PerbaikanJasa, id=no_dokumen)
    else:
        pj = get_object_or_404(PerbaikanJasa, no_dokumen=no_dokumen)

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    doc_key = pj.no_dokumen or str(pj.id)
    ga_form = None
    sam_form = None
    teknisi_form = None

    # Hak aksi sesuai role
    can_ga_edit = (profile.role in ['GA'] or request.user.is_superuser) and pj.status == 'WAITING_GA'
    can_sam_review = (profile.role in ['SAM'] or request.user.is_superuser) and pj.status == 'WAITING_SAM'
    can_teknisi_update = (profile.role in ['TEKNISI'] or request.user.is_superuser) and pj.status == 'APPROVED'

    if request.method == 'POST':
        action = request.POST.get('form_action')
        
        # 1. Action GA
        if action == 'submit_ga' and can_ga_edit:
            ga_form = PerbaikanJasaGAForm(request.POST, instance=pj)
            if ga_form.is_valid():
                item = ga_form.save(commit=False)
                item.status = 'WAITING_SAM'  # Diteruskan ke SAM
                item.save()
                messages.success(request, 'Estimasi bahan & harga berhasil ditambahkan. Diteruskan ke SAM.')
                return redirect('core:perbaikan_detail', no_dokumen=doc_key)

        # 2. Action SAM
        elif action == 'submit_sam' and can_sam_review:
            pilihan = request.POST.get('decision') or request.POST.get('action_type')
            sam_form = PerbaikanJasaSAMForm(request.POST, instance=pj)

            if sam_form.is_valid():
                urgensi = sam_form.cleaned_data.get('urgensi')
                alasan = (sam_form.cleaned_data.get('alasan_nok_sam') or '').strip()

                # --- 1. JIKA SAM TEKAN NOK (TOLAK) ---
                if pilihan == 'NOK':
                    # Cegatan: jika urgensi diisi padahal memilih NOK
                    if urgensi:
                        messages.error(
                            request,
                            'Peringatan: Jika memilih NOK (Tolak), pilihan Urgensi wajib dibiarkan kosong / jangan dipilih!'
                        )
                        return redirect('core:perbaikan_detail', no_dokumen=doc_key)

                    # Cegatan: jika alasan NOK kosong
                    if not alasan:
                        messages.error(
                            request,
                            'Gagal: Alasan penolakan (NOK) wajib diisi!'
                        )
                        return redirect('core:perbaikan_detail', no_dokumen=doc_key)

                    item = sam_form.save(commit=False)
                    item.status = 'REJECTED'
                    item.urgensi = None  # Memastikan urgensi tetap kosong di database
                    item.alasan_nok_sam = alasan
                    item.save()
                    messages.warning(request, f'Permintaan #{pj.id} ditolak (NOK).')
                    return redirect('core:perbaikan_detail', no_dokumen=doc_key)

                # --- 2. JIKA SAM TEKAN OK (APPROVE) ---
                elif pilihan == 'OK':
                    # Cegatan: jika urgensi tidak dipilih saat approve
                    if not urgensi:
                        messages.error(
                            request,
                            'Gagal: Silakan tentukan tingkat Urgensi perbaikan terlebih dahulu sebelum memilih OK.'
                        )
                        return redirect('core:perbaikan_detail', no_dokumen=doc_key)

                    item = sam_form.save(commit=False)
                    item.status = 'APPROVED'
                    item.urgensi = urgensi
                    item.save()
                    messages.success(request, f'Permintaan #{pj.id} disetujui & diteruskan ke Teknisi.')
                    return redirect('core:perbaikan_detail', no_dokumen=doc_key)

        # 3. Action Teknisi
        elif action == 'submit_teknisi' and can_teknisi_update:
            teknisi_form = PerbaikanJasaTeknisiForm(request.POST, request.FILES, instance=pj)
            if teknisi_form.is_valid():
                teknisi_form.save()
                messages.success(request, 'Progress pekerjaan berhasil diperbarui.')
                return redirect('core:perbaikan_detail', no_dokumen=doc_key)
    else:
        ga_form = PerbaikanJasaGAForm(instance=pj)
        sam_form = PerbaikanJasaSAMForm(instance=pj)
        teknisi_form = PerbaikanJasaTeknisiForm(instance=pj)

    return render(request, 'core/perbaikan_detail.html', {
        'pj': pj,
        'profile': profile,
        'can_ga_edit': can_ga_edit,
        'can_sam_review': can_sam_review,
        'can_teknisi_update': can_teknisi_update,
        'ga_form': ga_form,
        'sam_form': sam_form,
        'teknisi_form': teknisi_form,
    })


@login_required
def pembelian_list(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # 1. Hak Akses Dasar
    if profile.role in ['USER', 'TEKNISI'] and not request.user.is_superuser:
        qs = PembelianCabang.objects.filter(user=request.user)
    else:
        qs = PembelianCabang.objects.all()

    # 2. Filter & Pencarian
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    tahapan_filter = request.GET.get('tahapan', '').strip()
    tgl_mulai = request.GET.get('tgl_mulai', '').strip()
    tgl_selesai = request.GET.get('tgl_selesai', '').strip()

    if search_query:
        qs = qs.filter(
            Q(no_dokumen__icontains=search_query) |
            Q(nama__icontains=search_query) |
            Q(nik__icontains=search_query) |
            Q(items__nama_barang__icontains=search_query)
        ).distinct()

    if status_filter:
        qs = qs.filter(status_approval=status_filter)

    if tahapan_filter:
        qs = qs.filter(tahapan_ga=tahapan_filter)

    if tgl_mulai:
        
        qs = qs.filter(tanggal__gte=tgl_mulai)

    if tgl_selesai:
        qs = qs.filter(tanggal__lte=tgl_selesai)

    qs = qs.order_by('-created_at')

    paginator = Paginator(qs, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)


    return render(request, 'core/pembelian_list.html', {
        'items': page_obj,
        'profile': profile,
        'search_query': search_query,
        'status_filter': status_filter,
        'tahapan_filter': tahapan_filter,
        'tgl_mulai': tgl_mulai,
        'tgl_selesai': tgl_selesai,
        'status_choices': PembelianCabang.STATUS_APPROVAL_CHOICES,
        'tahapan_choices': PembelianCabang.TAHAPAN_GA_CHOICES,
    })

@login_required
def pembelian_create(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = PembelianCabangHeaderForm(request.POST)
        formset = ItemPembelianFormSet(request.POST, request.FILES)

        if form.is_valid() and formset.is_valid():
            pc = form.save(commit=False)
            pc.user = request.user
            pc.status_approval = 'WAITING_SAM'
            pc.save()

            formset.instance = pc
            formset.save()

            messages.success(request, f'Pengajuan pembelian {pc.no_dokumen} dengan {pc.items.count()} barang berhasil dikirim ke SAM.')
            return redirect('core:pembelian_list')
    else:
        form = PembelianCabangHeaderForm(initial={
            'nik': profile.nik,
            'nama': request.user.get_full_name() or request.user.username,
        })
        formset = ItemPembelianFormSet()

    return render(request, 'core/pembelian_create.html', {
        'form': form,
        'formset': formset
    })


@login_required
def pembelian_detail(request, no_dokumen):
    if no_dokumen.isdigit():
        pc = get_object_or_404(PembelianCabang, id=no_dokumen)
    else:
        pc = get_object_or_404(PembelianCabang, no_dokumen=no_dokumen)

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    doc_key = pc.no_dokumen or str(pc.id)

    can_sam_review = (profile.role == 'SAM' or request.user.is_superuser) and pc.status_approval == 'WAITING_SAM'
    can_sm_review = (profile.role == 'SM' or request.user.is_superuser) and pc.status_approval == 'WAITING_SM'
    can_ga_track = (profile.role == 'GA' or request.user.is_superuser) and pc.status_approval == 'APPROVED_TO_GA'

    if request.method == 'POST':
        action = request.POST.get('form_action')

        # 1. Approval SAM
        if action == 'submit_sam' and can_sam_review:
            sam_form = PembelianSAMReviewForm(request.POST, instance=pc)
            decision = request.POST.get('decision')
            if sam_form.is_valid():
                keterangan = (sam_form.cleaned_data.get('keterangan_sam') or '').strip()

                # Validasi jika tolak (NOK)
                if decision == 'NOK':
                    if len(keterangan) <= 10:
                        messages.error(request, 'Gagal: Keterangan penolakan (NOK) wajib diisi lebih dari 10 karakter!')
                        return redirect('core:pembelian_detail', no_dokumen=doc_key)

                    item = sam_form.save(commit=False)
                    item.is_approved_sam = False
                    item.status_approval = 'REJECTED_SAM'
                    item.save()
                    messages.warning(request, 'Permintaan ditolak oleh SAM (NOK).')
                    return redirect('core:pembelian_detail', no_dokumen=doc_key)
                
                elif decision == 'OK':
                    item = sam_form.save(commit=False)
                    item.is_approved_sam = True
                    item.status_approval = 'WAITING_SM'
                    item.save()
                    messages.success(request, 'Permintaan disetujui SAM, diteruskan ke SM.')
                    return redirect('core:pembelian_detail', no_dokumen=doc_key)

        # 2. Approval SM
        elif action == 'submit_sm' and can_sm_review:
            sm_form = PembelianSMReviewForm(request.POST, instance=pc)
            decision = request.POST.get('decision')
            if sm_form.is_valid():
                keterangan = (sm_form.cleaned_data.get('keterangan_sm') or '').strip()

                # Validasi jika tolak (NOK)
                if decision == 'NOK':
                    if len(keterangan) <= 10:
                        messages.error(request, 'Gagal: Keterangan penolakan (NOK) wajib diisi lebih dari 10 karakter!')
                        return redirect('core:pembelian_detail', no_dokumen=doc_key)

                    item = sm_form.save(commit=False)
                    item.is_approved_sm = False
                    item.status_approval = 'REJECTED_SM'
                    item.save()
                    messages.warning(request, 'Permintaan ditolak oleh SM (NOK).')
                    return redirect('core:pembelian_detail', no_dokumen=doc_key)

                elif decision == 'OK':
                    item = sm_form.save(commit=False)
                    item.is_approved_sm = True
                    item.status_approval = 'APPROVED_TO_GA'
                    item.tahapan_ga = 'PENDING'
                    item.save()
                    messages.success(request, 'Permintaan disetujui SM, diteruskan ke GA untuk pengadaan.')
                    return redirect('core:pembelian_detail', no_dokumen=doc_key)

        # 3. Tracking GA
        elif action == 'submit_ga' and can_ga_track:
            ga_form = PembelianGATrackingForm(request.POST, request.FILES, instance=pc)
            if ga_form.is_valid():
                ga_form.save()
                messages.success(request, 'Status tahapan pembelian berhasil diperbarui.')
                return redirect('core:pembelian_detail', no_dokumen=doc_key)

    sam_form = PembelianSAMReviewForm(instance=pc)
    sm_form = PembelianSMReviewForm(instance=pc)
    ga_form = PembelianGATrackingForm(instance=pc)

    return render(request, 'core/pembelian_detail.html', {
        'pc': pc,
        'profile': profile,
        'can_sam_review': can_sam_review,
        'can_sm_review': can_sm_review,
        'can_ga_track': can_ga_track,
        'sam_form': sam_form,
        'sm_form': sm_form,
        'ga_form': ga_form,
    })


@login_required
def pembelian_print_handover(request, no_dokumen):
    if no_dokumen.isdigit():
        pc = get_object_or_404(PembelianCabang, id=no_dokumen)
    else:
        pc = get_object_or_404(PembelianCabang, no_dokumen=no_dokumen)

    # Ambil personil GA pertama yang terdaftar
    ga_profile = UserProfile.objects.filter(role='GA').select_related('user').first()
    nama_ga = ga_profile.user.get_full_name() or ga_profile.user.username if ga_profile else "General Affair"

    # Ambil personil SM atau SAM (prioritas SM, jika tidak ada gunakan SAM)
    approver_profile = UserProfile.objects.filter(role__in=['SM', 'SAM']).select_related('user').first()
    nama_approver = approver_profile.user.get_full_name() or approver_profile.user.username if approver_profile else "Store Manager"
    jabatan_approver = approver_profile.get_role_display() if approver_profile else "SAM / SM"

    return render(request, 'core/pembelian_print_handover.html', {
        'pc': pc,
        'current_time': timezone.now(),
        'nama_ga': nama_ga,
        'nama_approver': nama_approver,
        'jabatan_approver': jabatan_approver,
    })

@login_required
def cetak_handover(request, no_dokumen):
    if no_dokumen.isdigit():
        pc = get_object_or_404(PembelianCabang, id=no_dokumen)
    else:
        pc = get_object_or_404(PembelianCabang, no_dokumen=no_dokumen)

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    doc_key = pc.no_dokumen or str(pc.id)

    # 1. Validasi Role: Hanya GA atau Superuser
    if profile.role != 'GA' and not request.user.is_superuser:
        messages.error(request, 'Akses ditolak: Cetak bukti handover hanya boleh dilakukan oleh GA.')
        return redirect('core:pembelian_detail', no_dokumen=doc_key)

    # 2. Validasi Status: Hanya barang yang sudah mencapai tahapan HANDOVER
    if pc.tahapan_ga != 'HANDOVER':
        messages.warning(request, 'Bukti handover belum dapat dicetak karena status barang belum Handover.')
        return redirect('core:pembelian_detail', no_dokumen=doc_key)

    return render(request, 'core/cetak_handover.html', {
        'pc': pc,
        'profile': profile
    })


def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            uid = form.cleaned_data['user_id']
            nama = form.cleaned_data['nama_lengkap']
            nik = form.cleaned_data['nik']
            nomor_hp = form.cleaned_data.get('nomor_hp', '').strip()
            role = form.cleaned_data['role']
            divisi = form.cleaned_data['divisi']
            password = form.cleaned_data['password']

            # Simpan ke tabel auth User bawaan Django
            user = User.objects.create_user(
                username=uid,
                password=password,
                first_name=nama
            )

            # Buat / perbarui profil tambahan
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'nik': nik,
                    'nomor_hp': nomor_hp,
                    'role': role,
                    'divisi': divisi
                }
            )

            messages.success(request, f'Akun {uid} berhasil dibuat! Silakan login.')
            return redirect('core:login')
    else:
        form = RegisterForm()

    return render(request, 'core/register.html', {'form': form})

@login_required
def export_laporan_excel(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Proteksi Akses: Hanya GA dan Superuser
    if profile.role != 'GA' and not request.user.is_superuser:
        messages.error(request, 'Akses ditolak: Fitur export laporan hanya dapat diakses oleh GA.')
        return redirect('core:dashboard')

    # Buat Workbook
    wb = openpyxl.Workbook()
    
    # Styling standar
    header_fill = PatternFill(start_color="0D47A1", end_color="0D47A1", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='D3D3D3'),
        right=Side(style='thin', color='D3D3D3'),
        top=Side(style='thin', color='D3D3D3'),
        bottom=Side(style='thin', color='D3D3D3')
    )

    # -------------------------------------------------------------
    # SHEET 1: LAPORAN PERBAIKAN & JASA
    # -------------------------------------------------------------
    ws_perbaikan = wb.active
    ws_perbaikan.title = "Perbaikan & Jasa"

    headers_perbaikan = [
        "No Tiket", "Tanggal", "NIK", "Nama Pemohon", "Divisi", 
        "Lokasi", "Objek", "Detail Kerusakan", "Kebutuhan Bahan (GA)", 
        "Estimasi Biaya", "Status Approval", "Urgensi", "Progress Teknisi", "Kendala"
    ]
    ws_perbaikan.append(headers_perbaikan)

    for cell in ws_perbaikan[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center

    perbaikan_qs = PerbaikanJasa.objects.all().order_by('-created_at')
    for pj in perbaikan_qs:
        ws_perbaikan.append([
            pj.no_dokumen,
            pj.tanggal.strftime("%d/%m/%Y") if pj.tanggal else "-",
            pj.nik,
            pj.nama,
            pj.divisi,
            pj.lokasi_spesifik,
            pj.objek,
            pj.detail,
            pj.deskripsi_kebutuhan_bahan or "-",
            float(pj.estimasi_harga) if pj.estimasi_harga else 0,
            pj.get_status_display(),
            pj.urgensi or "-",
            pj.progress_pekerjaan,
            pj.kendala or "-"
        ])

    # Format kolom estimasi biaya ke accounting format di Excel
    for row in ws_perbaikan.iter_rows(min_row=2, max_row=ws_perbaikan.max_row, min_col=10, max_col=10):
        for cell in row:
            cell.number_format = '"Rp "#,##0'

    # Auto lebar kolom Sheet 1
    for col in ws_perbaikan.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws_perbaikan.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # -------------------------------------------------------------
    # SHEET 2: LAPORAN PEMBELIAN CABANG
    # -------------------------------------------------------------
    ws_pembelian = wb.create_sheet(title="Pembelian Cabang")

    headers_pembelian = [
        "No PO", "Tanggal", "NIK", "Nama Pemohon", "Nama Barang", 
        "Peruntukan/Fungsi", "Estimasi Biaya", "Status Approval", 
        "Tahapan GA", "No Invoice"
    ]
    ws_pembelian.append(headers_pembelian)

    for cell in ws_pembelian[1]:
        cell.fill = PatternFill(start_color="B71C1C", end_color="B71C1C", fill_type="solid") # Merah PPJ
        cell.font = header_font
        cell.alignment = align_center

    pembelian_qs = PembelianCabang.objects.all().prefetch_related('items').order_by('-created_at')
    for pc in pembelian_qs:
        for item in pc.items.all():
            ws_pembelian.append([
                pc.no_dokumen,
                pc.tanggal.strftime("%d/%m/%Y") if pc.tanggal else "-",
                pc.nik,
                pc.nama,
                item.nama_barang,
                item.deskripsi_fungsi_peruntukan,
                float(item.estimasi_harga) if item.estimasi_harga else 0,
                pc.get_status_approval_display(),
                pc.get_tahapan_ga_display(),
                pc.nomor_invoice or "-"
            ])

    # Format kolom estimasi biaya Sheet 2
    for row in ws_pembelian.iter_rows(min_row=2, max_row=ws_pembelian.max_row, min_col=7, max_col=7):
        for cell in row:
            cell.number_format = '"Rp "#,##0'

    # Auto lebar kolom Sheet 2
    for col in ws_pembelian.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws_pembelian.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # Kunci waktu lokal WITA secara eksplisit
    tz_wita = ZoneInfo("Asia/Makassar")
    waktu_lokal = datetime.now(tz_wita)
    tanggal_str = waktu_lokal.strftime('%Y%m%d_%H%M%S')

    filename = f"Laporan_PPJ_IGR_GTO_{tanggal_str}.xlsx"

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    # Gunakan filename dan filename* (RFC 5987) agar browser tidak salah baca format
    response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*={filename}'
    
    # Cegah browser menyimpan cache file download
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    wb.save(response)
    return response