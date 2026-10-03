from .models import PerbaikanJasa, PembelianCabang, UserProfile

def pending_actions_processor(request):
    if not request.user.is_authenticated:
        return {}

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    role = profile.role

    badge_perbaikan = 0
    badge_pembelian = 0

    # 1. Hitung antrean untuk GA
    if role == 'GA':
        badge_perbaikan = PerbaikanJasa.objects.filter(status='WAITING_GA').count()
        badge_pembelian = PembelianCabang.objects.filter(
            status_approval='APPROVED_TO_GA'
        ).exclude(tahapan_ga='HANDOVER').count()

    # 2. Hitung antrean untuk SAM
    elif role == 'SAM':
        badge_perbaikan = PerbaikanJasa.objects.filter(status='WAITING_SAM').count()
        badge_pembelian = PembelianCabang.objects.filter(status_approval='WAITING_SAM').count()

    # 3. Hitung antrean untuk SM
    elif role == 'SM':
        badge_pembelian = PembelianCabang.objects.filter(status_approval='WAITING_SM').count()

    # 4. Hitung antrean untuk Teknisi
    elif role == 'TEKNISI':
        badge_perbaikan = PerbaikanJasa.objects.filter(
            status='APPROVED',
            progress_pekerjaan__in=['BELUM DIKERJAKAN', 'PROSES']
        ).count()

    return {
        'badge_perbaikan': badge_perbaikan,
        'badge_pembelian': badge_pembelian,
    }