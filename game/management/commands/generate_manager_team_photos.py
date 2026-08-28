"""Generate the first-team manager photos once per season."""

import base64
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from game.models import GameSeasonState, ManagerTeamPhoto, Player, SeasonFixture


class Command(BaseCommand):
    help = 'Erzeugt Mannschaftsfotos am ersten Pflichtspieltag mit gemini-2.5-flash-image.'

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int)

    def handle(self, *args, **options):
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise CommandError('GEMINI_API_KEY fehlt. Es gibt bewusst keinen Bild-Fallback.')

        state = GameSeasonState.objects.first()
        season = options['season'] if options['season'] is not None else (state.current_season if state else 0)
        first_matchday = (
            SeasonFixture.objects.filter(season=str(season))
            .order_by('matchday')
            .values_list('matchday', flat=True)
            .first()
        )
        if first_matchday is None:
            raise CommandError(f'Keine Pflichtspiele für Saison {season} vorhanden.')

        clubs = {}
        fixtures = SeasonFixture.objects.filter(
            season=str(season), matchday=first_matchday
        ).select_related('home_club__managed_by', 'away_club__managed_by')
        for fixture in fixtures:
            for club in (fixture.home_club, fixture.away_club):
                if club.managed_by_id:
                    clubs[club.pk] = club

        generated = 0
        for club in clubs.values():
            manager = club.managed_by
            photo, created = ManagerTeamPhoto.objects.get_or_create(
                manager=manager,
                season=season,
                defaults={'club': club},
            )
            if photo.generated_at and photo.image:
                continue
            players = list(
                Player.objects.filter(club=club)
                .order_by('position', 'last_name', 'first_name')
            )
            names = [player.full_name for player in players]
            if not names:
                continue
            png = self._generate(api_key, club.name, names)
            photo.club = club
            photo.roster_names = names
            photo.image.save(
                f'manager-{manager.pk}-season-{season}.png',
                ContentFile(png),
                save=False,
            )
            photo.generated_at = timezone.now()
            photo.save()
            generated += 1

        self.stdout.write(self.style.SUCCESS(f'{generated} Mannschaftsfoto(s) erzeugt.'))

    def _generate(self, api_key, club_name, names):
        count = len(names)
        rows = 3 if count <= 24 else 5
        prompt = (
            f'Create a realistic professional football team photo for {club_name}. '
            f'Show exactly {count} distinct adult players in {rows} orderly rows, all fully visible, '
            'dark neutral stadium background, balanced studio lighting, landscape 16:9, no text, '
            'no logos, no duplicate faces, PNG output. The roster order is: ' + ', '.join(names)
        )
        url = (
            'https://generativelanguage.googleapis.com/v1beta/models/'
            f'gemini-2.5-flash-image:generateContent?key={api_key}'
        )
        request = Request(
            url,
            data=json.dumps({
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'responseModalities': ['IMAGE']},
            }).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urlopen(request, timeout=180) as response:
                payload = json.load(response)
        except HTTPError as exc:
            raise CommandError(f'Gemini-Bilderzeugung fehlgeschlagen (HTTP {exc.code}).') from exc
        for candidate in payload.get('candidates', []):
            for part in candidate.get('content', {}).get('parts', []):
                inline = part.get('inlineData') or part.get('inline_data')
                if inline and inline.get('data'):
                    return base64.b64decode(inline['data'])
        raise CommandError('Gemini hat kein Bild zurückgegeben; es gibt bewusst keinen Fallback.')