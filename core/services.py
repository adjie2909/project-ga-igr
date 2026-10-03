import requests
from django.conf import settings

def kirim_wa_pengajuan(message, phone):
    """
    Mengirimkan payload pesan dan nomor HP ke endpoint Node.js
    """
    if not phone:
        print("⚠️ Nomor HP kosong, pesan dibatalkan.")
        return None

    payload = {
        "phone": phone,
        "message": message
    }

    try:
        response = requests.post(settings.WA_BOT_ENDPOINT, json=payload, timeout=5)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Gagal menghubungi endpoint Bot Node.js: {e}")
        return None