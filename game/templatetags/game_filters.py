from django import template

register = template.Library()


@register.filter
def shorten_name(name, max_len=16):
    """
    If a player name exceeds max_len characters, abbreviate the first name
    to its initial: "Vanderson de Oliveira" → "V. Oliveira"
    Names within max_len are returned unchanged and can wrap to 2 CSS lines.
    """
    if not name or len(name) <= max_len:
        return name
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}"
    return name[:max_len] + "\u2026"
