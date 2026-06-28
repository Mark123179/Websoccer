"""Management Command: fix_country_iso2

Einmaliger Audit + Korrektur für bestehende ``CountryNetwork``-Einträge, die
VOR der Eingabe-Validierung (Task #650) angelegt wurden und noch ungültige
ISO2-Codes enthalten können (Kleinbuchstaben, falsche Länge, Nicht-ASCII,
Leerzeichen).

Verhalten:
    - Findet alle Zeilen mit ``iso2``, das nicht exakt 2 Großbuchstaben (A–Z) ist
    - Eindeutig normalisierbare Codes (z. B. ``de`` -> ``DE``, ``" fr "`` -> ``FR``)
      werden korrigiert
    - Nicht eindeutig korrigierbare Codes (falsche Länge, Ziffern/Symbole,
      Nicht-ASCII) werden gemeldet, NICHT verändert
    - Würde eine Normalisierung mit einem bereits vorhandenen, gültigen Code
      kollidieren, wird die Zeile gemeldet statt gespeichert (manuelle Bereinigung)

Per Default ist der Command ein Dry-Run (read-only). Erst mit ``--apply`` werden
Änderungen geschrieben.

Verwendung:
    python manage.py fix_country_iso2            # nur anzeigen (Dry-Run)
    python manage.py fix_country_iso2 --apply    # Korrekturen schreiben
"""

from django.core.management.base import BaseCommand
from django.db import transaction


def is_valid_iso2(code):
    """True, wenn ``code`` exakt 2 ASCII-Großbuchstaben (A–Z) ist."""
    return (
        isinstance(code, str)
        and len(code) == 2
        and code.isascii()
        and code.isalpha()
        and code.isupper()
    )


def normalize_iso2(code):
    """Versucht, ``code`` eindeutig auf 2 ASCII-Großbuchstaben zu normalisieren.

    Gibt den normalisierten Code zurück oder ``None``, wenn keine eindeutige
    Korrektur möglich ist (z. B. falsche Länge, Ziffern, Nicht-ASCII).
    """
    if not isinstance(code, str):
        return None
    stripped = code.strip()
    # Validierung auf dem unverändert getrimmten Original – sonst würde z. B.
    # 'ß' fälschlich zu 'SS' (Längen-/ASCII-Wechsel durch .upper()) und als
    # automatisch korrigierbar behandelt, obwohl es manuell geprüft gehört.
    if not (len(stripped) == 2 and stripped.isascii() and stripped.isalpha()):
        return None
    return stripped.upper()


class Command(BaseCommand):
    help = ('Findet und korrigiert bestehende CountryNetwork-Zeilen mit '
            'ungültigen ISO2-Codes (Kleinbuchstaben, falsche Länge etc.).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true', default=False,
            help='Korrekturen tatsächlich schreiben (Default: nur Dry-Run).')

    def handle(self, *args, **options):
        from game.models import CountryNetwork

        apply_changes = options['apply']

        invalid = [
            cn for cn in CountryNetwork.objects.all().order_by('name')
            if not is_valid_iso2(cn.iso2)
        ]

        if not invalid:
            self.stdout.write(self.style.SUCCESS(
                'Alle ISO2-Codes sind bereits gültig (2 Großbuchstaben A–Z). '
                'Nichts zu tun.'))
            return

        self.stdout.write(self.style.WARNING(
            f'{len(invalid)} CountryNetwork-Zeile(n) mit ungültigem ISO2 gefunden:\n'))

        # Bereits vorhandene gültige Codes für Kollisionsprüfung.
        existing_valid = {
            cn.iso2 for cn in CountryNetwork.objects.all()
            if is_valid_iso2(cn.iso2)
        }

        fixable = []      # (cn, normalized)
        unfixable = []    # (cn, reason)

        # Innerhalb des Korrektur-Laufs neu belegte Codes (gegen Doppel-Normalisierung).
        claimed = set()

        for cn in invalid:
            normalized = normalize_iso2(cn.iso2)
            if normalized is None:
                unfixable.append((
                    cn,
                    'nicht eindeutig normalisierbar (falsche Länge / keine '
                    'ASCII-Buchstaben)'))
                continue
            if normalized in existing_valid or normalized in claimed:
                unfixable.append((
                    cn,
                    f'Normalisierung „{normalized}" kollidiert mit vorhandenem Code'))
                continue
            fixable.append((cn, normalized))
            claimed.add(normalized)

        for cn, normalized in fixable:
            self.stdout.write(
                f'  [korrigierbar] {cn.name}: '
                f'„{cn.iso2!r}" -> „{normalized}"')

        for cn, reason in unfixable:
            self.stdout.write(self.style.ERROR(
                f'  [manuell] {cn.name} (pk={cn.pk}): '
                f'„{cn.iso2!r}" – {reason}'))

        if not apply_changes:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE(
                f'Dry-Run: {len(fixable)} korrigierbar, '
                f'{len(unfixable)} manuell zu bereinigen. '
                'Mit --apply schreiben.'))
            return

        if not fixable:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'Keine automatisch korrigierbaren Zeilen – nichts geschrieben. '
                f'{len(unfixable)} Zeile(n) brauchen manuelle Bereinigung.'))
            return

        with transaction.atomic():
            for cn, normalized in fixable:
                cn.iso2 = normalized
                cn.save(update_fields=['iso2', 'updated_at'])

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{len(fixable)} Zeile(n) korrigiert.'))
        if unfixable:
            self.stdout.write(self.style.WARNING(
                f'{len(unfixable)} Zeile(n) brauchen weiterhin manuelle '
                'Bereinigung (siehe [manuell] oben).'))
