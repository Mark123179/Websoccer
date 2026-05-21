from django import template

register = template.Library()


@register.filter
def format_market_value(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return "—"

    if value >= 1_000_000:
        millions = value / 1_000_000
        formatted = f"{millions:.1f}".replace(".", ",")
        if formatted.endswith(",0"):
            formatted = formatted[:-2]
        return f"{formatted} Mio. €"
    else:
        thousands = value / 1_000
        formatted = f"{thousands:.1f}".replace(".", ",")
        if formatted.endswith(",0"):
            formatted = formatted[:-2]
        return f"{formatted} Tsd. €"
