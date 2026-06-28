from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count

from game.models import (
    Club,
    DataSource,
    Player,
    PlayerCMTAttributeProfile,
    PlayerCMTProfile,
)


CAREER_END_CLUB_NAME = 'Karrierende'


def _has_text(value):
    return bool((value or '').strip())


def _cached_image_exists(player):
    profile = getattr(player, 'cmt_profile', None)
    if profile and _has_text(profile.player_image_cached_path):
        cached_path = profile.player_image_cached_path.strip()
        if Path(cached_path).is_absolute():
            return Path(cached_path).exists()
        return (settings.BASE_DIR / cached_path).exists()

    if not player.fm_inside_id or not player.club_id:
        return False

    club = player.club
    if not club or not club.fm_inside_id:
        return False

    composite = (
        settings.BASE_DIR
        / 'game'
        / 'static'
        / 'game'
        / 'images'
        / 'player_composites'
        / f'{player.fm_inside_id}_{club.fm_inside_id}_home.png'
    )
    return composite.exists()


class Command(BaseCommand):
    help = 'Auditiert die Vollstaendigkeit von Spieler-/CMT-Daten read-only.'

    def handle(self, *args, **options):
        players = Player.objects.all()
        active_players = players.exclude(club__name=CAREER_END_CLUB_NAME)
        cmt_profiles = PlayerCMTProfile.objects.select_related('player')
        cmt_attributes = PlayerCMTAttributeProfile.objects.all()
        cmt_source = DataSource.objects.filter(
            code=DataSource.CODE_CMTRACKER
        ).first()

        cmt_player_ids = set(cmt_profiles.values_list('player_id', flat=True))
        cmt_external_player_ids = set()
        if cmt_source:
            cmt_external_player_ids = set(
                cmt_source.player_external_ids.values_list('player_id', flat=True)
            )

        active_players_for_image = list(
            active_players.select_related('club', 'cmt_profile')
        )
        cached_image_player_ids = {
            player.pk
            for player in active_players_for_image
            if _cached_image_exists(player)
        }

        self.stdout.write('Player data completeness audit')
        self.stdout.write('')
        self._write_metric('total players', players.count())
        self._write_metric(
            'active players ohne Karrierende',
            active_players.count(),
        )
        self._write_metric('CMT profiles', cmt_profiles.count())
        self._write_metric('CMT attributes', cmt_attributes.count())
        self._write_metric(
            'auto-created CMT players',
            players.filter(wsc_player_id__startswith='CMT').count(),
        )
        self._write_metric(
            'free agents',
            players.filter(club__isnull=True, loan_status='none').count(),
        )
        self._write_metric(
            'nationalities filled',
            active_players.exclude(nationalities='').count(),
        )
        self._write_metric(
            'CMT image_url filled',
            cmt_profiles.exclude(player_image_url='').count(),
        )
        self._write_metric('CMT cached images', len(cached_image_player_ids))

        self.stdout.write('')
        self.stdout.write(
            'Club | players | cmt profiles | missing transfermarkt_id | '
            'missing fm_inside_id | missing sofifa_id | missing nationality | '
            'missing cached image'
        )
        self.stdout.write('-' * 130)

        clubs = (
            Club.objects.exclude(name=CAREER_END_CLUB_NAME)
            .annotate(players_count=Count('player'))
            .filter(players_count__gt=0)
            .order_by('name')
        )

        for club in clubs:
            club_players = list(
                active_players
                .filter(club=club)
                .select_related('club', 'cmt_profile')
            )
            cmt_count = sum(1 for player in club_players if player.pk in cmt_player_ids)
            missing_sofifa = sum(
                1 for player in club_players
                if player.pk not in cmt_external_player_ids
            )
            missing_cached = sum(
                1 for player in club_players
                if player.pk not in cached_image_player_ids
            )

            self.stdout.write(
                f'{club.name} | '
                f'{len(club_players)} | '
                f'{cmt_count} | '
                f'{sum(1 for player in club_players if not player.transfermarkt_id)} | '
                f'{sum(1 for player in club_players if not player.fm_inside_id)} | '
                f'{missing_sofifa} | '
                f'{sum(1 for player in club_players if not _has_text(player.nationalities))} | '
                f'{missing_cached}'
            )

    def _write_metric(self, label, value):
        self.stdout.write(f'{label}: {value}')
