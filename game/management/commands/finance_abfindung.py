"""Abfindung buchen (Spec Kap. 4) — Produktionspfad für die Monatspflege.

Todesfall und Karriereende sind Realdaten-Ereignisse (kein Sim-Event):
Dieses Command ist der Admin-/Pflegepfad. Es bucht die Abfindung für den
abgebenden Verein und hängt den Spieler anschließend auf den
Karrierende-Pseudo-Verein um (abschaltbar via --keep-club).

Idempotent je (Spieler, Grund) — Wiederholungsläufe buchen nichts doppelt.
"""
from django.core.management.base import BaseCommand, CommandError

from game.club_history import is_career_end_club_id
from game.economy.severance import (
    GRUND_KARRIEREENDE,
    GRUND_TOD,
    book_abfindung,
    retire_player,
)


class Command(BaseCommand):
    help = (
        'Bucht eine Abfindung (Todesfall/Karriereende) und verschiebt den '
        'Spieler zum Karrierende-Pseudo-Verein.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--player-id', type=int, required=True,
            help='Player-PK des betroffenen Spielers.',
        )
        parser.add_argument(
            '--grund', choices=[GRUND_TOD, GRUND_KARRIEREENDE], required=True,
            help="Abfindungsgrund: 'tod' oder 'karriereende'.",
        )
        parser.add_argument(
            '--saison', default=None,
            help='Saison-String (Default: aktuelle Sim-Saison).',
        )
        parser.add_argument(
            '--keep-club', action='store_true',
            help='Nur buchen — Spieler NICHT auf Karrierende umhängen.',
        )

    def handle(self, *args, **options):
        from game.models import Club, Player

        try:
            player = Player.objects.select_related('club').get(
                pk=options['player_id'])
        except Player.DoesNotExist:
            raise CommandError(
                f"Spieler mit ID {options['player_id']} nicht gefunden.")

        if player.club_id and is_career_end_club_id(player.club_id):
            self.stdout.write(self.style.WARNING(
                f'{player.first_name} {player.last_name} ist bereits beim '
                'Karrierende-Pseudo-Verein — nichts zu tun.'))
            return

        if options['keep_club']:
            tx = book_abfindung(player, options['grund'], options['saison'])
        else:
            karrierende = (
                Club.objects.filter(name__iexact='Karrierende').first()
                or Club.objects.filter(name__iexact='Karriereende').first()
            )
            if karrierende is None:
                raise CommandError(
                    'Karrierende-Pseudo-Verein nicht gefunden — '
                    'mit --keep-club nur buchen oder Verein anlegen.')
            tx = retire_player(
                player, karrierende, grund=options['grund'],
                saison=options['saison'])

        if tx is not None:
            self.stdout.write(self.style.SUCCESS(
                f'Abfindung gebucht: {tx.betrag} € an {tx.club.name} '
                f'({tx.beschreibung}).'))
        else:
            self.stdout.write(
                'Keine Buchung fällig (Faktor 0 / bereits gebucht / '
                'kein Verein).')
        if not options['keep_club']:
            self.stdout.write(
                f'{player.first_name} {player.last_name} → Karrierende.')
