"""Audit-Übersicht für CMT-Spielerprofile und Metadaten-Vollständigkeit."""

from django.core.management.base import BaseCommand
from django.db.models import Q

from game.models import Player, PlayerCMTAttributeProfile, PlayerCMTProfile


class Command(BaseCommand):
    help = 'Gibt einen Überblick über CMT-Profil-Vollständigkeit aus.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--missing-images', action='store_true',
            help='Listet Spieler mit fehlenden lokal gecachten Bildern auf.',
        )

    def handle(self, *args, **options):
        show_missing = options['missing_images']

        active_total   = Player.objects.filter(club__isnull=False).count()
        all_players    = Player.objects.count()
        cmt_total      = PlayerCMTProfile.objects.count()
        cmt_attr_total = PlayerCMTAttributeProfile.objects.count()

        nat_filled        = PlayerCMTProfile.objects.exclude(nationality='').count()
        second_nat_filled = PlayerCMTProfile.objects.exclude(second_nationality='').count()
        img_url_filled    = PlayerCMTProfile.objects.exclude(player_image_url='').count()
        img_cached_filled = PlayerCMTProfile.objects.exclude(player_image_cached_path='').count()
        img_missing       = PlayerCMTProfile.objects.exclude(player_image_url='').filter(
            player_image_cached_path=''
        ).count()

        player_nat_filled = Player.objects.exclude(nationalities='').count()

        sep = '─' * 52

        self.stdout.write(sep)
        self.stdout.write('  CMT-Profil-Audit')
        self.stdout.write(sep)
        self.stdout.write(f'  Aktive Spieler (mit Verein):     {active_total:>5}')
        self.stdout.write(f'  Alle Spieler (inkl. vereinslos): {all_players:>5}')
        self.stdout.write(sep)
        self.stdout.write(f'  PlayerCMTProfile:                {cmt_total:>5}')
        self.stdout.write(f'  PlayerCMTAttributeProfile:       {cmt_attr_total:>5}')
        self.stdout.write(sep)
        self.stdout.write(f'  Player.nationalities gefüllt:    {player_nat_filled:>5} / {all_players}')
        self.stdout.write(f'  CMT nationality gefüllt:         {nat_filled:>5} / {cmt_total}')
        self.stdout.write(f'  CMT second_nationality gefüllt:  {second_nat_filled:>5} / {cmt_total}')
        self.stdout.write(sep)
        self.stdout.write(f'  CMT player_image_url gefüllt:    {img_url_filled:>5} / {cmt_total}')
        self.stdout.write(f'  CMT player_image_cached_path:    {img_cached_filled:>5} / {cmt_total}')
        self.stdout.write(f'  Fehlende lokale Bilder:          {img_missing:>5}')
        self.stdout.write(sep)

        if img_missing > 0:
            self.stdout.write(
                self.style.WARNING(f'  {img_missing} Profil(e) mit URL aber ohne lokales Bild:')
            )
            qs_missing = (
                PlayerCMTProfile.objects
                .exclude(player_image_url='')
                .filter(player_image_cached_path='')
                .select_related('player')
                .order_by('player__last_name', 'player__first_name')
            )
            for prof in qs_missing:
                name = getattr(prof.player, 'full_name', f'Player {prof.player_id}')
                self.stdout.write(f'    - {name}  [{prof.player_image_url[:60]}]')

        if show_missing and img_missing == 0:
            self.stdout.write(self.style.SUCCESS('  Alle Bilder lokal gecacht. ✓'))
