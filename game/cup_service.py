"""
game/cup_service.py — DFB-Pokal / K.-O.-Wettbewerb Service

Öffentliche API:
    calculate_opening_round(n)               → dict {matches, byes}
    generate_dummy_clubs(league, count, name_prefix) → list[Club]
    build_cup_participants(cup_season, ...)  → list[Club]
    draw_cup_round(cup_round, participants)  → list[CupFixture]
    simulate_cup_fixture(fixture)            → CupFixture
    advance_cup_round(cup_round)             → CupRound | None
    schedule_cup_round(cup_round)            → CupRound
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from django.db import transaction

from .random_utils import stable_seed


# ── Rundencode-Tabelle ────────────────────────────────────────────────────────

ROUND_CODES: dict[int, str] = {
    32: 'round_of_32',
    16: 'round_of_16',
    8:  'quarter_final',
    4:  'semi_final',
    2:  'final',
}

ROUND_DISPLAY_NAMES: dict[str, str] = {
    'round_of_32': '1. Runde (32)',
    'round_of_16': '2. Runde (16)',
    'quarter_final': 'Viertelfinale',
    'semi_final': 'Halbfinale',
    'final': 'Finale',
}


def _round_display_name(code: str) -> str:
    """Gibt den deutschen Anzeigenamen für einen Rundencode zurück."""
    return ROUND_DISPLAY_NAMES.get(code, code.replace('_', ' ').title())


class CupServiceError(Exception):
    """Basis-Exception für Pokal-Service-Fehler."""


class CupRoundAlreadyDrawnError(CupServiceError):
    """Runde wurde bereits ausgelost und Teilnehmer weichen ab."""


class CupRoundAlreadyExistsError(CupServiceError):
    """Nächste Runde existiert bereits."""


class CupRoundNotCompleteError(CupServiceError):
    """Nicht alle Spiele der Runde sind abgeschlossen."""


class CupInvalidParticipantsError(CupServiceError):
    """Teilnehmerliste ist ungültig (leer, Duplikate, zu wenige)."""


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def calculate_opening_round(n: int) -> dict:
    """Berechnet Spiele und Freilose für eine beliebige Teilnehmerzahl.

    Die erste Runde eines K.-o.-Turniers muss die Teilnehmerzahl auf die
    nächste 2er-Potenz reduzieren. Freilose entstehen auch bei geraden
    Teilnehmerzahlen, die keine 2er-Potenz sind (z. B. 36 → 4 Spiele + 28 Freilose).

    Beispiele:
        32 → {matches: 16, byes: 0}
        36 → {matches: 4,  byes: 28}
        16 → {matches: 8,  byes: 0}
    """
    if n < 2:
        raise ValueError(f'Mindestens 2 Teilnehmer erforderlich, erhalten: {n}')
    target = 1 << (n.bit_length() - 1)  # größte 2er-Potenz ≤ n
    if n == target:
        return {'matches': n // 2, 'byes': 0}
    matches = n - target
    byes = target - matches
    return {'matches': matches, 'byes': byes}


# ── Dummy-Club-Generator ──────────────────────────────────────────────────────

_DUMMY_POSITIONS: list[tuple[str, int]] = [
    ('TW', 2),
    ('LV', 2),
    ('IV', 4),
    ('RV', 2),
    ('LM', 2),
    ('ZM', 2),
    ('RM', 2),
    ('ST', 2),
]


def generate_dummy_clubs(
    league,
    count: int = 18,
    name_prefix: str = '2. Bundesliga Dummy',
) -> list:
    """Legt idempotent `count` Dummy-Clubs in der angegebenen Liga an.

    Bei erneutem Aufruf werden bereits vorhandene Clubs (nach Name) nicht
    doppelt angelegt — get_or_create-Logik pro Club.

    Jeder Club erhält:
    - 18 Spieler (2 TW, 2 LV, 4 IV, 2 RV, 2 LM, 2 ZM, 2 RM, 2 ST)
    - PlayerSourceRating (SOURCE_FM) mit Basiswerten
    - Standardtaktik 4-4-2 via ensure_default_tactic()

    Gibt die Liste aller (neu oder bereits vorhandenen) Clubs zurück.
    """
    from .models import Club, Player, PlayerSourceRating
    from .match_readiness import ensure_default_tactic

    clubs = []
    with transaction.atomic():
        for i in range(1, count + 1):
            club_name = f'{name_prefix} #{i:02d}'
            short_name = f'DUM{i:02d}'[:20]

            club, created = Club.objects.get_or_create(
                name=club_name,
                defaults={
                    'short_name':   short_name,
                    'founded_year': 2000,
                    'budget':       1_000_000,
                    'league':       league,
                    'fan_popularity': 30,
                },
            )
            if not created:
                if club.league_id != league.pk:
                    club.league = league
                    club.save(update_fields=['league'])
            else:
                _create_dummy_squad(club)

            ensure_default_tactic(club)
            clubs.append(club)

    return clubs


def _create_dummy_squad(club) -> None:
    """Erzeugt 18 Dummy-Spieler für einen neu angelegten Club."""
    from .models import Player, PlayerSourceRating

    slot = 0
    for position, count in _DUMMY_POSITIONS:
        for j in range(1, count + 1):
            slot += 1
            is_gk = position == 'TW'
            player = Player.objects.create(
                first_name='Dummy',
                last_name=f'{position}{j}',
                position=position,
                main_position_1=position,
                club=club,
                nationalities='Deutschland',
                age=25 + (slot % 10),
            )
            attr = {
                'ausdauer':   70,
                'tempo':      60,
                'kraft':      60,
                'technik':    60,
                'dribbling':  60,
                'passspiel':  60,
                'flanken':    55,
                'abschluss':  55 if not is_gk else 30,
                'kopfball':   55,
                'zweikampf':  60,
                'defensivstellung': 60,
                'uebersicht': 60,
                'elfmeter':   60,
            }
            if is_gk:
                attr.update({'tw_reflexe': 72, 'tw_fangsicherheit': 68})

            PlayerSourceRating.objects.create(
                player=player,
                source=PlayerSourceRating.SOURCE_FM,
                rating=60,
                **attr,
            )


# ── Teilnehmer-Builder ────────────────────────────────────────────────────────

def build_cup_participants(
    cup_season,
    bundesliga,
    zweitliga,
    bl_count: int = 18,
    zweite_bl_count: int = 14,
    fallback_by_id: bool = True,
) -> list:
    """Setzt die Pokalteilnehmer als unveränderlichen Snapshot in CupSeason.

    Nimmt alle `bl_count` Bundesligisten + `zweite_bl_count` Zweitligisten.
    Für die initiale Saison ohne Ligatabelle: `fallback_by_id=True` →
    erste `zweite_bl_count` Zweitligisten sortiert nach club.id.

    Die Teilnehmer werden als M2M-Snapshot gespeichert und sind damit
    unabhängig von späteren Tabellenänderungen.
    """
    bl_clubs = list(bundesliga.club_set.order_by('id')[:bl_count])
    if fallback_by_id:
        zwb_clubs = list(zweitliga.club_set.order_by('id')[:zweite_bl_count])
    else:
        from .models import LeagueStandings
        standings = (
            LeagueStandings.objects
            .filter(league=zweitliga)
            .order_by('position')[:zweite_bl_count]
        )
        zwb_clubs = [s.club for s in standings]
        if len(zwb_clubs) < zweite_bl_count:
            existing_ids = {c.id for c in zwb_clubs}
            extras = list(
                zweitliga.club_set
                .exclude(id__in=existing_ids)
                .order_by('id')[:zweite_bl_count - len(zwb_clubs)]
            )
            zwb_clubs.extend(extras)

    participants = bl_clubs + zwb_clubs
    if len(participants) < 2:
        raise CupInvalidParticipantsError(
            f'Zu wenige Teilnehmer: {len(participants)}'
        )

    cup_season.participants.set(participants)
    cup_season.status = cup_season.STATUS_RUNNING
    cup_season.save(update_fields=['status'])
    return participants


# ── Auslosungs-Engine ─────────────────────────────────────────────────────────

def draw_cup_round(cup_round, participants: list) -> list:
    """Legt deterministisch alle CupFixtures einer Runde an.

    Idempotent: Wenn die Runde bereits Fixtures enthält, werden diese
    unverändert zurückgegeben. Eine ausgeloste Runde mit ANDEREN
    Teilnehmern löst CupRoundAlreadyDrawnError aus.

    Alles-oder-Nichts: Entweder alle Fixtures werden angelegt oder keine
    (transaction.atomic + select_for_update).

    Seed: stable_seed("cup-draw:{competition_id}:{season}:{round_number}")
    """
    from .models import CupFixture

    if len(participants) < 2:
        raise CupInvalidParticipantsError(
            f'Mindestens 2 Teilnehmer benötigt, erhalten: {len(participants)}'
        )

    participant_ids = {c.id for c in participants}
    if len(participant_ids) != len(participants):
        raise CupInvalidParticipantsError('Teilnehmerliste enthält Duplikate.')

    with transaction.atomic():
        cup_round_locked = (
            type(cup_round).objects
            .select_for_update()
            .get(pk=cup_round.pk)
        )

        existing = list(cup_round_locked.fixtures.order_by('bracket_position'))
        if existing:
            existing_club_ids: set[int] = set()
            for f in existing:
                if f.home_club_id:
                    existing_club_ids.add(f.home_club_id)
                if f.away_club_id:
                    existing_club_ids.add(f.away_club_id)
                if f.winner_club_id:
                    existing_club_ids.add(f.winner_club_id)
            if existing_club_ids != participant_ids:
                raise CupRoundAlreadyDrawnError(
                    'Runde wurde bereits mit anderen Teilnehmern ausgelost.'
                )
            return existing

        clubs = sorted(participants, key=lambda c: c.id)
        seed = stable_seed(
            'cup-draw',
            cup_round_locked.cup_season.competition_id,
            cup_round_locked.cup_season.season,
            cup_round_locked.round_number,
        )
        rng = random.Random(seed)
        rng.shuffle(clubs)

        opening = calculate_opening_round(len(clubs))
        fixtures_to_create: list[CupFixture] = []
        bracket_pos = 1

        bye_count = opening['byes']
        bye_clubs = clubs[:bye_count]
        match_clubs = clubs[bye_count:]

        for club in bye_clubs:
            fixtures_to_create.append(CupFixture(
                cup_round=cup_round_locked,
                bracket_position=bracket_pos,
                home_club=club,
                away_club=None,
                winner_club=club,
                is_bye=True,
                status=CupFixture.STATUS_BYE,
            ))
            bracket_pos += 1

        for k in range(0, len(match_clubs), 2):
            home = match_clubs[k]
            away = match_clubs[k + 1]
            fixtures_to_create.append(CupFixture(
                cup_round=cup_round_locked,
                bracket_position=bracket_pos,
                home_club=home,
                away_club=away,
                is_bye=False,
                status=CupFixture.STATUS_SCHEDULED,
            ))
            bracket_pos += 1

        CupFixture.objects.bulk_create(fixtures_to_create)
        return list(cup_round_locked.fixtures.order_by('bracket_position'))


# ── Spielsimulation ───────────────────────────────────────────────────────────

def simulate_cup_fixture(fixture) -> object:
    """Simuliert ein Pokalspiel und persistiert alle Ergebnisse.

    Ruft simulate_ko_match() auf und schreibt danach über die
    kanonische write_simulated_match_stats()-Pipeline (Frische,
    Verletzungen, Karten, Statistiken). Sperren werden vorab
    dekrementiert (Pflichtspiel-Logik).

    Die gesamte Pipeline läuft in einer Datenbank-Transaktion.
    Schlägt write_simulated_match_stats() fehl, wird kein CupFixture
    als gespielt markiert.

    Gibt das aktualisierte CupFixture-Objekt zurück.
    """
    from .models import SimulatedMatch, Club as _Club
    from .match_engine import simulate_ko_match
    from .season_service import (
        write_simulated_match_stats,
        _decrement_suspensions_for_clubs,
    )

    if fixture.is_bye or fixture.status == fixture.STATUS_BYE:
        raise CupServiceError('Freilos-Fixtures können nicht simuliert werden.')
    if fixture.status == fixture.STATUS_PLAYED:
        raise CupServiceError('Spiel wurde bereits simuliert.')
    if not fixture.home_club or not fixture.away_club:
        raise CupServiceError('Heim- oder Auswärtsverein fehlt.')

    # Sperr-Countdown vorab dekrementieren (Pflichtspiel-Logik).
    # Explizit außerhalb der atomaren Pipeline, da _decrement_suspensions_for_clubs
    # kein Rollback-kritisches Statement ist.
    _decrement_suspensions_for_clubs([fixture.home_club_id, fixture.away_club_id])

    # Spiel simulieren — außerhalb der atomaren Transaktion, da der Match Engine
    # keine DB-Schreiboperationen durchführt.
    data = simulate_ko_match(fixture.home_club, fixture.away_club)

    winner_id = data.get('winner_club_id')
    decided_by = data.get('decided_by', 'regular_time')

    home_goals_et_raw = data.get('home_goals_et', 0) or 0
    away_goals_et_raw = data.get('away_goals_et', 0) or 0

    raw_h90 = data.get('home_goals_90')
    raw_a90 = data.get('away_goals_90')
    if raw_h90 is not None:
        home_goals_90 = raw_h90
        away_goals_90 = raw_a90 or 0
    else:
        home_goals_90 = data.get('home_goals', 0) - (home_goals_et_raw if decided_by != 'regular_time' else 0)
        away_goals_90 = data.get('away_goals', 0) - (away_goals_et_raw if decided_by != 'regular_time' else 0)

    with transaction.atomic():
        sm = SimulatedMatch.objects.create(
            home_club=fixture.home_club,
            away_club=fixture.away_club,
            home_goals=data['home_goals'],
            away_goals=data['away_goals'],
            report_data=data,
            match_type='pokal',
        )

        # Kanonische Pipeline — Stats, Verletzungen, Frische, Karten.
        # Fehler hier brechen die Transaktion: kein teilweise-persistierter Zustand.
        write_simulated_match_stats(sm, data)

        if winner_id:
            try:
                winner_club = _Club.objects.get(pk=winner_id)
            except _Club.DoesNotExist:
                winner_club = fixture.home_club
        else:
            winner_club = fixture.home_club

        fixture.simulated_match = sm
        fixture.home_goals_90 = home_goals_90
        fixture.away_goals_90 = away_goals_90
        fixture.home_goals_et = home_goals_et_raw if decided_by in ('extra_time', 'penalties') else None
        fixture.away_goals_et = away_goals_et_raw if decided_by in ('extra_time', 'penalties') else None
        fixture.home_penalties = data.get('home_penalties')
        fixture.away_penalties = data.get('away_penalties')
        fixture.decided_by = decided_by
        fixture.winner_club = winner_club
        fixture.status = fixture.STATUS_PLAYED
        fixture.save()

    return fixture


# ── Rundenfortschritt ─────────────────────────────────────────────────────────

def advance_cup_round(cup_round) -> object | None:
    """Schließt die aktuelle Runde ab und legt die nächste an.

    Atomar + select_for_update: Gleichzeitige Aufrufe erzeugen keine
    doppelte Folgerunde.

    Gibt die neue CupRound zurück, oder None wenn das Finale abgeschlossen wurde.
    """
    from .models import CupRound, CupFixture

    with transaction.atomic():
        cup_round_locked = (
            CupRound.objects
            .select_for_update()
            .prefetch_related('fixtures')
            .get(pk=cup_round.pk)
        )

        fixtures = list(cup_round_locked.fixtures.all())
        if not fixtures:
            raise CupRoundNotCompleteError('Runde enthält keine Spiele.')

        incomplete = [
            f for f in fixtures
            if f.status not in (CupFixture.STATUS_PLAYED, CupFixture.STATUS_BYE)
        ]
        if incomplete:
            raise CupRoundNotCompleteError(
                f'{len(incomplete)} Spiel(e) noch nicht abgeschlossen.'
            )

        cup_round_locked.status = CupRound.STATUS_COMPLETED
        cup_round_locked.save(update_fields=['status'])

        winners = [f.winner_club for f in fixtures if f.winner_club]
        cup_season = cup_round_locked.cup_season

        if len(winners) == 1:
            cup_season.winner_club = winners[0]
            cup_season.status = cup_season.STATUS_COMPLETED
            cup_season.save(update_fields=['winner_club', 'status'])
            return None

        next_round_number = cup_round_locked.round_number + 1
        if cup_season.rounds.filter(round_number=next_round_number).exists():
            raise CupRoundAlreadyExistsError(
                f'Runde {next_round_number} existiert bereits.'
            )

        round_code = ROUND_CODES.get(len(winners), f'round_of_{len(winners)}')
        next_round = CupRound.objects.create(
            cup_season=cup_season,
            round_number=next_round_number,
            round_code=round_code,
            status=CupRound.STATUS_PENDING,
        )
        draw_cup_round(next_round, winners)
        return next_round


def simulate_cup_round(cup_round) -> list:
    """Simuliert alle noch offenen Spiele einer Runde.

    Freilose werden übersprungen.
    Gibt Liste der aktualisierten CupFixtures zurück.
    """
    from .models import CupFixture

    fixtures = list(
        cup_round.fixtures.filter(
            status=CupFixture.STATUS_SCHEDULED,
            is_bye=False,
        )
    )
    results = []
    for fixture in fixtures:
        try:
            results.append(simulate_cup_fixture(fixture))
        except CupServiceError:
            pass
    return results


# ── Terminplanung ─────────────────────────────────────────────────────────────

def schedule_cup_round(cup_round, season: str | None = None) -> object:
    """Setzt cup_round.scheduled_date auf den frühesten konfliktfreien Di/Mi.

    Startpunkt:
    - Runde 1: Saisonbeginn + 14 Tage (saison-relativ aus cup_season.season
      sofern parsierbar, sonst heute + 14 Tage)
    - Folgerunden: scheduled_date der vorherigen Runde + 7 Tage

    Ablehnen wenn:
    - Ein beteiligter Club an dem Tag ein Ligaspiel hat (SeasonFixture)
    - Ein beteiligter Club bereits ein anderes Pokalspiel hat

    Maximales Suchfenster: 60 Tage.

    Wirft CupServiceError wenn kein konfliktfreier Termin gefunden werden kann.
    """
    from .models import CupFixture, SeasonFixture

    all_fixtures = list(cup_round.fixtures.filter(is_bye=False))
    club_ids: set[int] = set()
    for f in all_fixtures:
        if f.home_club_id:
            club_ids.add(f.home_club_id)
        if f.away_club_id:
            club_ids.add(f.away_club_id)

    cup_season = cup_round.cup_season
    prev_round = (
        cup_season.rounds
        .filter(round_number__lt=cup_round.round_number)
        .order_by('-round_number')
        .first()
    )

    if prev_round and prev_round.scheduled_date:
        start = prev_round.scheduled_date + timedelta(days=7)
    else:
        # Saison-relativ: "2025/26" → Startjahr 2025, August (Pokal-Beginn)
        start = _season_start_date(cup_season.season) + timedelta(days=14)

    existing_cup_dates = set(
        cup_season.rounds
        .exclude(pk=cup_round.pk)
        .filter(scheduled_date__isnull=False)
        .values_list('scheduled_date', flat=True)
    )

    season_str = season or cup_season.season
    if club_ids:
        liga_dates = set(
            SeasonFixture.objects
            .filter(home_club_id__in=club_ids, season=season_str)
            .values_list('scheduled_date', flat=True)
        ) | set(
            SeasonFixture.objects
            .filter(away_club_id__in=club_ids, season=season_str)
            .values_list('scheduled_date', flat=True)
        )
    else:
        liga_dates = set()

    blocked = (liga_dates | existing_cup_dates) - {None}

    candidate = start
    for _ in range(60):
        if candidate.weekday() in (1, 2) and candidate not in blocked:
            cup_round.scheduled_date = candidate
            cup_round.status = type(cup_round).STATUS_SCHEDULED
            cup_round.save(update_fields=['scheduled_date', 'status'])
            return cup_round
        candidate += timedelta(days=1)

    raise CupServiceError(
        f'Kein konfliktfreier Di/Mi-Termin in den nächsten 60 Tagen ab {start} gefunden.'
    )


def _season_start_date(season: str) -> date:
    """Parst 'YYYY/YY' oder 'YYYY' → date(YYYY, 8, 1) als saisonaler Startpunkt."""
    try:
        year = int(season.split('/')[0])
        return date(year, 8, 1)
    except (ValueError, AttributeError):
        return date.today()
