from django import template
from decimal import Decimal

register = template.Library()

@register.filter(name='rupiah')
def rupiah(value):
    if value is None or value == '':
        return "Rp 0"
    
    try:
        # Konversi ke int/pembulatan jika desimal .00
        val = float(value)
        # Format ribuan standar Python dengan koma: 1,500,000
        formatted = f"{val:,.0f}"
        # Ubah koma ribuan menjadi titik standar Indonesia: 1.500.000
        formatted_id = formatted.replace(',', '.')
        return f"Rp {formatted_id}"
    except (ValueError, TypeError):
        return f"Rp {value}"