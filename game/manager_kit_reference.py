"""The three approved reference kits, not a manager's career history."""

from django.templatetags.static import static


def reference_kits():
    return [
        {
            'glb': static(f'game/models/kits/{code}_away.glb'),
            'img': static(f'game/images/kits/hanger-{code}.png'),
            'W': width,
            'H': height,
        }
        for code, width, height in [
            ('1026', 483, 688),
            ('1050', 591, 822),
            ('1052', 520, 734),
        ]
    ]