"""Management Command: seed_country_networks

Legt die ersten echten ``CountryNetwork``-Einträge an, damit die Scouting-Karte
echte scoutbare/im-Aufbau-Länder anzeigt. Die echte Business-Logik greift:

    - Land mit Netzwerk + Pool >= COUNTRY_THRESHOLD  -> ``scoutable``
    - Land mit Netzwerk, Pool darunter               -> ``building``

Die echte Poolgröße wird NIE gespeichert; nur Community-/Aktivitätspunkte, aus
denen ``coverage_percent`` abgeleitet wird. Idempotent über ``update_or_create``.

Verwendung:
    python manage.py seed_country_networks
    python manage.py seed_country_networks --dry-run
    python manage.py seed_country_networks --reset   # vorhandene Punkte überschreiben
"""

from django.core.management.base import BaseCommand


# Startnetzwerke: echte Fußballnationen über mehrere Kontinente verteilt.
# (iso2, community_points, activity_points). Werte sind kalibrierbare Startwerte
# und bestimmen nur die angezeigte Abdeckung (coverage_percent), nicht den Pool.
SEED_NETWORKS = [
    ('DE', 70, 40),   # Deutschland – starkes Heimnetzwerk
    ('TR', 55, 25),   # Türkei
    ('BE', 30, 15),   # Belgien
    ('BR', 45, 30),   # Brasilien
    ('AR', 20, 10),   # Argentinien – noch im Aufbau
]


class Command(BaseCommand):
    help = 'Legt die ersten echten CountryNetwork-Einträge für die Scouting-Karte an.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False,
                            help='Nur anzeigen, was angelegt/aktualisiert würde.')
        parser.add_argument('--reset', action='store_true', default=False,
                            help='Vorhandene Punkte mit den Startwerten überschreiben.')

    def handle(self, *args, **options):
        from game.models import CountryNetwork
        from game.scouting.constants import COUNTRIES

        dry_run = options['dry_run']
        reset = options['reset']

        created, updated, skipped = 0, 0, 0
        for iso2, community, activity in SEED_NETWORKS:
            rec = COUNTRIES.get(iso2)
            if not rec:
                self.stderr.write(self.style.WARNING(
                    f'  {iso2}: nicht im COUNTRIES-Katalog – übersprungen.'))
                continue

            existing = CountryNetwork.objects.filter(iso2=iso2).first()
            if existing and not reset:
                skipped += 1
                self.stdout.write(f'  {iso2} {rec["name"]}: existiert bereits – unverändert.')
                continue

            if dry_run:
                verb = 'aktualisieren' if existing else 'anlegen'
                self.stdout.write(f'  [dry-run] {iso2} {rec["name"]}: würde {verb} '
                                  f'(community={community}, activity={activity}).')
                continue

            _, was_created = CountryNetwork.objects.update_or_create(
                iso2=iso2,
                defaults={
                    'name': rec['name'],
                    'continent': rec['continent'],
                    'region': rec['region'],
                    'community_points': community,
                    'activity_points': activity,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  {iso2} {rec["name"]}: angelegt.'))
            else:
                updated += 1
                self.stdout.write(self.style.SUCCESS(f'  {iso2} {rec["name"]}: aktualisiert.'))

        if dry_run:
            self.stdout.write(self.style.NOTICE('Dry-run – keine Änderungen geschrieben.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Fertig: {created} angelegt, {updated} aktualisiert, {skipped} unverändert.'))
