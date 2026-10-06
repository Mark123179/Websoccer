from decimal import Decimal
from django import template
from game.club_import.presentation import DISPLAY_LABELS
from game.club_import.presentation import loan_line

register = template.Library()
register.filter("loan_line", loan_line)


@register.filter
def package_label(value):
    return DISPLAY_LABELS.get(value, value)


@register.filter
def euro_de(value):
    if value is None:
        return "Unbekannt"
    return f"{Decimal(value):,.0f}".replace(",", ".")
