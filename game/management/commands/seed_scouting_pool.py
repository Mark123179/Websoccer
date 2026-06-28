"""Management Command: seed_scouting_pool

Füllt den Scouting-Spielerpool mit vereinslosen, scoutbaren Poolspielern je
Nation, damit Länder tatsächlich auf ``scoutable`` schalten (siehe
``game.scouting.coverage``):

    Pool je Nation >= COUNTRY_THRESHOLD (50)  -> Land wird ``scoutable``

Ohne diesen Schritt bleibt der Dev-Pool leer (0) und jedes Land zeigt nur
"Netzwerk im Aufbau" (``building``), obwohl ein CountryNetwork existiert.

Erzeugte Spieler:
    - ``club = None`` (vereinslos, Pflicht für Scoutbarkeit)
    - ``pool_status = SCOUTABLE``
    - moderate Stärke/Potential, sodass sie NICHT als Top-Star/Top-Talent
      reserviert werden (diese wären nie über Scouting verpflichtbar)
    - eigenes ``PlayerStrengthProfile`` (sonst Default-Stärke 50)

Alle Seed-Spieler tragen eine ``wsc_player_id`` mit Präfix ``POOLSEED-<ISO>-``,
damit ``--reset`` sie gezielt entfernen kann (echte Importspieler bleiben
unangetastet). Die Ziehung ist über ``--seed`` deterministisch.

Verwendung:
    python manage.py seed_scouting_pool                      # DE, 60 Spieler
    python manage.py seed_scouting_pool --countries DE,TR,BR --per-country 60
    python manage.py seed_scouting_pool --all --per-country 55
    python manage.py seed_scouting_pool --reset --countries DE
    python manage.py seed_scouting_pool --dry-run
"""

import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Mehrsprachige Vor-/Nachnamen-Pools (rein generisch, nur für den Dev-Pool).
FIRST_NAMES = [
    'Luca', 'Mateo', 'Noah', 'Liam', 'Leon', 'Elias', 'Felix', 'Jonas',
    'Diego', 'Bruno', 'Marco', 'Pablo', 'Hugo', 'Enzo', 'Theo', 'Nico',
    'Kai', 'Finn', 'Emir', 'Ivan', 'Milan', 'Luka', 'Adam', 'Yusuf',
    'Samuel', 'David', 'Daniel', 'Tobias', 'Anton', 'Erik', 'Oscar', 'Henri',
    'Mathis', 'Aaron', 'Joel', 'Rafael', 'Sergio', 'Andrei', 'Pavel', 'Omar',
]
LAST_NAMES = [
    'Berger', 'Hofmann', 'Schubert', 'Moreau', 'Lefebvre', 'Rossi', 'Conti',
    'Silva', 'Santos', 'Pereira', 'Garcia', 'Lopez', 'Fernandez', 'Novak',
    'Horvat', 'Kovac', 'Petrov', 'Ivanov', 'Yilmaz', 'Demir', 'Kaya',
    'Andersen', 'Nielsen', 'Larsson', 'Johansson', 'Okafor', 'Mensah',
    'Diallo', 'Traore', 'Mbeki', 'Tanaka', 'Sato', 'Kim', 'Park', 'Al-Farsi',
    'Nowak', 'Kowalski', 'Popescu', 'Marin', 'Vidal',
]

# Positionsverteilung (Hauptposition) – grob realistische Kaderstruktur.
POSITION_WEIGHTS = [
    ('TW', 3),
    ('IV', 6), ('LV', 3), ('RV', 3),
    ('DM', 3), ('ZM', 6), ('LM', 2), ('RM', 2),
    ('OM', 3), ('LF', 2), ('RF', 2),
    ('ST', 5),
]


class Command(BaseCommand):
    help = ('Füllt den Scouting-Pool mit vereinslosen, scoutbaren Poolspielern '
            'je Nation, damit Länder auf "scoutable" schalten.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--countries', default='DE',
            help='Komma-Liste der ISO2-Codes (Default: DE). Ignoriert bei --all.')
        parser.add_argument(
            '--all', action='store_true', default=False,
            help='Alle Länder aus dem COUNTRIES-Katalog befüllen.')
        parser.add_argument(
            '--per-country', type=int, default=60,
            help='Zielanzahl scoutbarer Poolspieler je Nation (Default: 60).')
        parser.add_argument(
            '--seed', type=int, default=646,
            help='RNG-Seed für deterministische Generierung (Default: 646).')
        parser.add_argument(
            '--reset', action='store_true', default=False,
            help='Vorhandene Seed-Poolspieler (Präfix POOLSEED-) zuvor löschen.')
        parser.add_argument(
            '--dry-run', action='store_true', default=False,
            help='Nur anzeigen, was passieren würde – keine Schreibvorgänge.')

    def handle(self, *args, **options):
        from game.scouting.constants import COUNTRIES
        from game.scouting.coverage import COUNTRY_THRESHOLD

        per_country = options['per_country']
        if per_country < 0:
            raise CommandError('--per-country darf nicht negativ sein.')
        if per_country == 0 and not options['reset']:
            raise CommandError('--per-country=0 ist nur zusammen mit --reset erlaubt.')

        if options['all']:
            isos = list(COUNTRIES.keys())
        else:
            isos = [c.strip().upper() for c in options['countries'].split(',') if c.strip()]

        unknown = [iso for iso in isos if iso not in COUNTRIES]
        if unknown:
            raise CommandError(
                f'Unbekannte ISO2-Codes (nicht im COUNTRIES-Katalog): {", ".join(unknown)}')
        if not isos:
            raise CommandError('Keine Länder angegeben.')

        dry_run = options['dry_run']
        reset = options['reset']
        rng = random.Random(options['seed'])

        if per_country < COUNTRY_THRESHOLD:
            self.stdout.write(self.style.WARNING(
                f'Hinweis: --per-country={per_country} < COUNTRY_THRESHOLD'
                f'={COUNTRY_THRESHOLD}; betroffene Länder bleiben "building".'))

        total_created, total_deleted = 0, 0
        for iso in isos:
            created, deleted = self._seed_country(
                iso, per_country, rng, reset, dry_run)
            total_created += created
            total_deleted += deleted

        if dry_run:
            self.stdout.write(self.style.NOTICE('Dry-run – keine Änderungen geschrieben.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Fertig: {total_created} Poolspieler angelegt, '
                f'{total_deleted} entfernt.'))
            self._report_status(isos)

    # ── Pro Land ─────────────────────────────────────────────────────────────
    def _seed_country(self, iso, per_country, rng, reset, dry_run):
        from game.models import Player, PlayerStrengthProfile
        from game.scouting.constants import COUNTRIES

        rec = COUNTRIES[iso]
        nationality = self._nationality_for_iso(iso, rec['name'])
        prefix = f'POOLSEED-{iso}-'

        existing_qs = Player.objects.filter(wsc_player_id__startswith=prefix)
        existing = existing_qs.count()

        deleted = 0
        if reset and existing:
            if dry_run:
                self.stdout.write(
                    f'  [dry-run] {iso} {rec["name"]}: würde {existing} Seed-Spieler löschen.')
            else:
                deleted, _ = existing_qs.delete()
                existing = 0

        need = per_country - existing
        if need <= 0:
            self.stdout.write(
                f'  {iso} {rec["name"]}: bereits {existing} Seed-Spieler – nichts zu tun.')
            return 0, deleted

        if dry_run:
            self.stdout.write(
                f'  [dry-run] {iso} {rec["name"]}: würde {need} Poolspieler anlegen '
                f'(Nationalität "{nationality}").')
            return 0, deleted

        positions = [p for p, w in POSITION_WEIGHTS for _ in range(w)]
        start_index = existing + 1
        created = 0
        with transaction.atomic():
            for offset in range(need):
                index = start_index + offset
                player = self._build_player(
                    Player, iso, prefix, index, nationality, positions, rng)
                player.save()
                base = player._seed_base_strength
                profile = PlayerStrengthProfile(
                    player=player,
                    base_strength=base,
                    form_modifier=0,
                    freshness=100,
                )
                profile.save()
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'  {iso} {rec["name"]}: {created} Poolspieler angelegt '
            f'(jetzt {existing + created}).'))
        return created, deleted

    # ── Einzelner Spieler ────────────────────────────────────────────────────
    def _build_player(self, Player, iso, prefix, index, nationality, positions, rng):
        from decimal import Decimal

        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        position = rng.choice(positions)
        age = rng.randint(18, 31)

        # Stärke moderat halten: nie >= TOP_STAR_STRENGTH (84) und kein
        # Top-Talent (<=21 & potential >= 88), damit die Spieler über die
        # normale Scouting-Suche verpflichtbar bleiben.
        base = rng.randint(58, 80)
        potential = min(85, base + rng.randint(0, 8))
        if age <= 21:
            potential = min(potential, 85)

        # grober, plausibler Marktwert aus Stärke/Alter abgeleitet.
        mv = (base - 50) * 180_000
        if age <= 23:
            mv = int(mv * 1.25)
        market_value = Decimal(max(mv, 50_000))

        player = Player(
            wsc_player_id=f'{prefix}{index:04d}',
            first_name=first,
            last_name=last,
            nationalities=nationality,
            age=age,
            position=position,
            primary_position=position,
            main_position_1=position,
            potential=potential,
            market_value=market_value,
            club=None,
            pool_status=Player.POOL_STATUS_SCOUTABLE,
            scouting_category=self._category_for(base, age, potential),
            admin_reviewed=True,
        )
        player._seed_base_strength = base
        return player

    @staticmethod
    def _category_for(base, age, potential):
        if age <= 21 and potential >= base + 4:
            return 'talent'
        if base >= 76:
            return 'stammkraft'
        if base >= 70:
            return 'rotation'
        if base >= 64:
            return 'ergaenzung'
        return 'backup'

    # ── Nationalität → korrekte ISO-Rückzuordnung ────────────────────────────
    @staticmethod
    def _nationality_for_iso(iso, default_name):
        """Liefert einen Nationalitätsnamen, der via geo wieder auf ``iso`` mappt.

        Der Katalogname (z. B. "England") mappt nicht immer auf den Karten-ISO
        (GB → "GB-ENG"); dann wird ein passender Name aus den Flag-Stammdaten
        gewählt, damit die Poolzählung das Land korrekt erkennt.
        """
        from game.scouting.geo import nationality_to_iso2
        if nationality_to_iso2(default_name) == iso:
            return default_name
        from game.models import COUNTRY_FLAG_ASSETS
        for name, frec in COUNTRY_FLAG_ASSETS.items():
            if (frec.get('code') or '').upper() == iso:
                return name
        return default_name

    # ── Status-Report ────────────────────────────────────────────────────────
    def _report_status(self, isos):
        from game.scouting.coverage import pool_counts_by_country, country_status
        from game.scouting.constants import COUNTRIES

        counts = pool_counts_by_country()
        self.stdout.write('Status (echte Poolzählung, nur serverseitig):')
        for iso in isos:
            status = country_status(iso, counts=counts)
            self.stdout.write(
                f'  {iso} {COUNTRIES[iso]["name"]}: Pool={counts.get(iso, 0)} → {status}')
