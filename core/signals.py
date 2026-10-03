from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import PembelianCabang, PerbaikanJasa, UserProfile
from .services import kirim_wa_pengajuan


def get_phone_by_role(role_name):
    """
    Mengambil nomor HP user pertama yang memiliki role tertentu di core_userprofile.
    Role: 'GA', 'SAM', 'SM', 'TEKNISI'
    """
    profile = UserProfile.objects.filter(
        role=role_name,
        nomor_hp__isnull=False
    ).exclude(nomor_hp='').first()

    return profile.nomor_hp if profile else None


def get_user_phone(user):
    """
    Mengambil nomor HP pemohon.
    """
    if not user:
        return None
    profile = UserProfile.objects.filter(user=user).first()
    return profile.nomor_hp if (profile and profile.nomor_hp) else None


# ========================================================
# PRE-SAVE: DETEKSI PERUBAHAN STATUS
# ========================================================
@receiver(pre_save, sender=PerbaikanJasa)
def track_status_perbaikan(sender, instance, **kwargs):
    if instance.pk:
        old_obj = PerbaikanJasa.objects.filter(pk=instance.pk).first()
        instance._old_status = old_obj.status if old_obj else None
    else:
        instance._old_status = None


@receiver(pre_save, sender=PembelianCabang)
def track_status_pembelian(sender, instance, **kwargs):
    if instance.pk:
        old_obj = PembelianCabang.objects.filter(pk=instance.pk).first()
        instance._old_status = old_obj.status_approval if old_obj else None
    else:
        instance._old_status = None


# ========================================================
# 1. ALUR NOTIFIKASI PERBAIKAN
# User -> GA (WAITING_GA) -> SAM (WAITING_SAM) -> TEKNISI (APPROVED) / REJECTED
# ========================================================
@receiver(post_save, sender=PerbaikanJasa)
def notif_alur_perbaikan(sender, instance, created, **kwargs):
    no_dok = instance.no_dokumen or f"PJ-{instance.pk}"
    pemohon = instance.user
    nama_pemohon = instance.nama or pemohon.username
    status_sekarang = instance.status
    status_lama = getattr(instance, '_old_status', None)

    # A. User Baru Saja Mengajukan Kendala -> Notif ke GA
    if created:
        no_ga = get_phone_by_role('GA')
        if no_ga:
            pesan = (
                f"*PENGAJUAN KENDALA BARU*\n"
                f"====================================\n\n"
                f"No. Dokumen : {no_dok}\n"
                f"Pemohon     : {nama_pemohon} ({instance.divisi})\n"
                f"Objek       : {instance.objek}\n"
                f"Lokasi      : {instance.lokasi_spesifik}\n"
                f"Status      : Menunggu Estimasi & Review GA\n\n"
                f"Silakan periksa detail kendala dan input estimasi bahan/harga."
            )
            kirim_wa_pengajuan(pesan, phone=no_ga)
        return

    # B. Jika Terjadi Perubahan Status Approval
    if status_sekarang != status_lama:
        # GA Sudah Input Estimasi -> Lanjut ke SAM
        if status_sekarang == 'WAITING_SAM':
            no_sam = get_phone_by_role('SAM')
            if no_sam:
                pesan = (
                    f"*REVIEW KENDALA PERBAIKAN (UNTUK SAM)*\n"
                    f"====================================\n\n"
                    f"No. Dokumen : {no_dok}\n"
                    f"Pemohon     : {nama_pemohon} ({instance.divisi})\n"
                    f"Objek       : {instance.objek}\n"
                    f"Estimasi    : Rp {instance.estimasi_harga:,.0f}" if instance.estimasi_harga else f"Estimasi    : -\n"
                    f"Status      : Diteruskan GA, Menunggu Approval SAM\n\n"
                    f"Mohon verifikasi urgensi dan lakukan persetujuan di sistem GA."
                )
                kirim_wa_pengajuan(pesan, phone=no_sam)

        # SAM Menyetujui -> Diteruskan ke Teknisi & Pemohon
        elif status_sekarang == 'APPROVED':
            # 1. Kirim Penugasan ke Teknisi
            no_teknisi = get_phone_by_role('TEKNISI')
            if no_teknisi:
                pesan_teknisi = (
                    f"*PENUGASAN PERBAIKAN BARU*\n"
                    f"====================================\n\n"
                    f"No. Dokumen : {no_dok}\n"
                    f"Lokasi/User : {nama_pemohon} ({instance.lokasi_spesifik})\n"
                    f"Objek       : {instance.objek}\n"
                    f"Urgensi     : {instance.get_urgensi_display() if instance.urgensi else '-'}\n"
                    f"Status      : Diapprove SAM (Siap Dikerjakan)\n\n"
                    f"Silakan koordinasikan dengan pemohon dan update progress pekerjaan."
                )
                kirim_wa_pengajuan(pesan_teknisi, phone=no_teknisi)

            # 2. Kirim Info ke Pemohon
            no_pemohon = get_user_phone(pemohon)
            if no_pemohon:
                pesan_user = (
                    f"*PENGAJUAN PERBAIKAN DISETUJUI*\n\n"
                    f"Halo {nama_pemohon}, pengajuan perbaikan Anda (*{no_dok}*) "
                    f"telah disetujui oleh SAM dan telah ditugaskan ke Teknisi."
                )
                kirim_wa_pengajuan(pesan_user, phone=no_pemohon)

        # Jika Ditolak (REJECTED) -> Kirim ke Pemohon
        elif status_sekarang == 'REJECTED':
            no_pemohon = get_user_phone(pemohon)
            if no_pemohon:
                alasan = f"\nAlasan: {instance.alasan_nok_sam}" if instance.alasan_nok_sam else ""
                pesan_tolak = (
                    f"*PENGAJUAN PERBAIKAN DITOLAK*\n\n"
                    f"Halo {nama_pemohon}, pengajuan perbaikan Anda (*{no_dok}*) "
                    f"telah ditolak.{alasan}\n\n"
                    f"Silakan periksa catatan di dashboard GA."
                )
                kirim_wa_pengajuan(pesan_tolak, phone=no_pemohon)


# ========================================================
# 2. ALUR NOTIFIKASI PEMBELIAN CABANG
# User -> SAM (WAITING_SAM) -> SM (WAITING_SM) -> GA Eksekusi (APPROVED_TO_GA)
# ========================================================
@receiver(post_save, sender=PembelianCabang)
def notif_alur_pembelian(sender, instance, created, **kwargs):
    no_dok = instance.no_dokumen or f"PB-{instance.pk}"
    pemohon = instance.user
    nama_pemohon = instance.nama or pemohon.username
    status_sekarang = instance.status_approval
    status_lama = getattr(instance, '_old_status', None)

    # A. User Mengajukan Pembelian Baru -> Notif ke SAM
    if created:
        no_sam = get_phone_by_role('SAM')
        if no_sam:
            pesan = (
                f"*PENGAJUAN PEMBELIAN BARU*\n"
                f"====================================\n\n"
                f"No. Dokumen : {no_dok}\n"
                f"Pemohon     : {nama_pemohon}\n"
                f"Total Item  : {instance.total_item}\n"
                f"Estimasi    : Rp {instance.total_estimasi:,.0f}\n"
                f"Status      : Menunggu Approval Tahap 1 (SAM)\n\n"
                f"Silakan verifikasi permohonan melalui dashboard GA."
            )
            kirim_wa_pengajuan(pesan, phone=no_sam)
        return

    # B. Jika Terjadi Perubahan Status Approval
    if status_sekarang != status_lama:
        # SAM Menyetujui -> Lanjut ke SM
        if status_sekarang == 'WAITING_SM':
            no_sm = get_phone_by_role('SM')
            if no_sm:
                pesan = (
                    f"*APPROVAL PEMBELIAN TAHAP 2 (UNTUK SM)*\n"
                    f"====================================\n\n"
                    f"No. Dokumen : {no_dok}\n"
                    f"Pemohon     : {nama_pemohon}\n"
                    f"Total Item  : {instance.total_item}\n"
                    f"Estimasi    : Rp {instance.total_estimasi:,.0f}\n"
                    f"Status      : Disetujui SAM, Menunggu Persetujuan SM\n\n"
                    f"Silakan masuk ke sistem GA untuk memberikan persetujuan final."
                )
                kirim_wa_pengajuan(pesan, phone=no_sm)

        # SM Menyetujui Final -> Notif ke GA untuk Eksekusi Pembelian
        elif status_sekarang == 'APPROVED_TO_GA':
            # 1. Notif Instruksi Pembelian ke Tim GA
            no_ga = get_phone_by_role('GA')
            if no_ga:
                pesan_ga = (
                    f"*EKSEKUSI PEMBELIAN BARANG (GA)*\n"
                    f"====================================\n\n"
                    f"No. Dokumen : {no_dok}\n"
                    f"Pemohon     : {nama_pemohon}\n"
                    f"Estimasi    : Rp {instance.total_estimasi:,.0f}\n"
                    f"Status      : DISETUJUI LENGKAP (SAM & SM)\n\n"
                    f"Silakan tim GA segera memproses pencarian vendor/toko dan pembelian barang."
                )
                kirim_wa_pengajuan(pesan_ga, phone=no_ga)

            # 2. Notif Sukses ke Pemohon
            no_pemohon = get_user_phone(pemohon)
            if no_pemohon:
                pesan_user = (
                    f"*PENGAJUAN PEMBELIAN DISETUJUI*\n\n"
                    f"Halo {nama_pemohon}, pengajuan pembelian Anda (*{no_dok}*) "
                    f"telah disetujui oleh SAM & SM, dan saat ini sedang dalam proses eksekusi pengadaan oleh tim GA."
                )
                kirim_wa_pengajuan(pesan_user, phone=no_pemohon)

        # Jika Ditolak SAM atau SM
        elif status_sekarang in ['REJECTED_SAM', 'REJECTED_SM']:
            no_pemohon = get_user_phone(pemohon)
            if no_pemohon:
                penolak = "SAM" if status_sekarang == 'REJECTED_SAM' else "SM"
                ket = instance.keterangan_sam if penolak == "SAM" else instance.keterangan_sm
                alasan = f"\nCatatan: {ket}" if ket else ""
                pesan_tolak = (
                    f"*PENGAJUAN PEMBELIAN DITOLAK*\n\n"
                    f"Halo {nama_pemohon}, pengajuan pembelian Anda (*{no_dok}*) "
                    f"telah ditolak oleh {penolak}.{alasan}\n\n"
                    f"Silakan cek sistem GA untuk informasi lebih lanjut."
                )
                kirim_wa_pengajuan(pesan_tolak, phone=no_pemohon)