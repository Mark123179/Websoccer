from django.core.management.base import BaseCommand
from django.db.models import Q

from game.models import NATIONALITY_ALIASES, Player


def _normalize_segment(segment):
    """Normiert ein einzelnes Nationalitäts-Segment via NATIONALITY_ALIASES.

    Gibt (normalized, changed) zurück.
    """
    raw = segment.strip()
    if not raw:
        return raw, False
    key = raw.lower()
    canonical = NATIONALITY_ALIASES.get(key)
    if canonical and canonical != raw:
        return canonical, True
    return raw, False


def _normalize_field(value):
    """Normiert ein Komma-getrenntes Nationalitäts-Feld.

    Gibt (normalized_value, changed, unknowns) zurück.
    unknowns ist eine Liste von Rohwerten, die in der Alias-Map nicht gefunden wurden
    und auch kein Kanonschlüssel in COUNTRY_FLAG_ASSETS sind.
    """
    from game.models import COUNTRY_FLAG_ASSETS

    if not value:
        return value, False, []

    normalized_value = value.replace(';', ',')
    changed = normalized_value != value
    segments = [s.strip() for s in normalized_value.split(',') if s.strip()]
    result_parts = []
    unknowns = []

    for seg in segments:
        normalized, was_changed = _normalize_segment(seg)
        result_parts.append(normalized)
        if was_changed:
            changed = True
        if normalized not in COUNTRY_FLAG_ASSETS:
            unknowns.append(normalized)

    return ', '.join(result_parts), changed, unknowns


class Command(BaseCommand):
    help = (
        'Normiert nationalities- und nt_nationality-Felder aller Spieler via '
        'NATIONALITY_ALIASES (englische Namen → deutsche Kanonform). '
        'Tipp: Danach backfill_nt_nationality ausführen, um leere nt_nationality-Felder '
        'aus dem normalisierten nationalities-Feld zu befüllen.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Zeigt Änderungen an, ohne sie zu speichern.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run — keine Änderungen werden gespeichert.'))

        qs = Player.objects.filter(
            Q(nationalities__gt='') | Q(nt_nationality__gt='')
        )

        total = qs.count()
        self.stdout.write(f'{total} Spieler mit Nationalitätsdaten gefunden.')

        normalized_count = 0
        all_unknowns = {}

        for player in qs.iterator():
            player_changed = False
            update_fields = []

            new_nat, nat_changed, nat_unknowns = _normalize_field(player.nationalities)
            if nat_changed:
                player_changed = True
                update_fields.append('nationalities')
                if not dry_run:
                    player.nationalities = new_nat
                if dry_run:
                    self.stdout.write(
                        f'  [dry] {player.full_name}: nationalities '
                        f'{player.nationalities!r} → {new_nat!r}'
                    )

            for u in nat_unknowns:
                all_unknowns[u] = all_unknowns.get(u, 0) + 1

            nt_raw = player.nt_nationality
            if nt_raw:
                new_nt, nt_changed, nt_unknowns = _normalize_field(nt_raw)
                if nt_changed:
                    player_changed = True
                    update_fields.append('nt_nationality')
                    if not dry_run:
                        player.nt_nationality = new_nt
                    if dry_run:
                        self.stdout.write(
                            f'  [dry] {player.full_name}: nt_nationality '
                            f'{nt_raw!r} → {new_nt!r}'
                        )
                for u in nt_unknowns:
                    all_unknowns[u] = all_unknowns.get(u, 0) + 1

            if player_changed:
                normalized_count += 1
                if not dry_run and update_fields:
                    player.save(update_fields=update_fields)

        no_nationality_count = Player.objects.filter(
            nationalities='', nt_nationality=''
        ).count()

        self.stdout.write('')
        self.stdout.write('── Abschluss-Report ─────────────────────────────────')
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'Dry-run: {normalized_count} Spieler würden normiert.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{normalized_count} Spieler normiert.'
            ))
        self.stdout.write(f'{no_nationality_count} Spieler ohne Nationalität.')

        if all_unknowns:
            self.stdout.write(
                self.style.WARNING(
                    f'{len(all_unknowns)} unbekannte Werte (nicht in NATIONALITY_ALIASES '
                    'und nicht in COUNTRY_FLAG_ASSETS):'
                )
            )
            for val, cnt in sorted(all_unknowns.items(), key=lambda x: -x[1]):
                self.stdout.write(f'  {cnt:>4}×  {val!r}')
        else:
            self.stdout.write('Keine unbekannten Werte.')
