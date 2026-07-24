"""Saison-Finanzjobs (Spec Kap. 15): finance_season_open / finance_season_close.

finance_season_open (Saisonstart):
  1. SeasonEconomySnapshot sicherstellen (MW-Median, Gehalts-Anker)
  2. TV-Ländertöpfe nach Koeffizienten-Rang einfrieren (TVPot)
  3. Sponsorangebote für alle Ligavereine generieren
Idempotent via SeasonFinanceState.opened_at.

finance_season_close (Saisonende):
  1. TV-Platz-/Koeffanteil je abgeschlossener Liga ausschütten
  2. Pokalprämien-Backstop (sync_cup_premiums für alle Pokalsaisons)
  3. Zieljäger-Sponsorboni (nur bereits ausgewertete, erreichte Ziele)
  4. Landes-/Vereinskoeffizienten fortschreiben (Carry-Forward-Stub)
  5. Saison-Finanzreport in SeasonFinanceState.report_json
closed_at wird erst gesetzt, wenn ALLE Ligen der Saison durchgespielt
sind — vorher ist jeder Aufruf ein idempotenter Teil-Lauf (Ligen, die
schon fertig sind, werden ausgeschüttet; der Rest wartet).

Fallschirmzahlungen (Kap. 7.4) laufen NICHT automatisch — es existiert
noch keine Auf-/Abstiegsmechanik (Servicepfad: tv.book_fallschirm).
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def _liga_ist_komplett(league, saison: str) -> bool:
    from game.models import SeasonFixture

    qs = SeasonFixture.objects.filter(league=league, season=saison)
    return qs.exists() and not qs.filter(is_played=False).exists()


def _saison_ligen(saison: str) -> list:
    from game.models import League, SeasonFixture

    league_ids = (
        SeasonFixture.objects.filter(season=saison)
        .values_list('league_id', flat=True).distinct()
    )
    return list(League.objects.filter(pk__in=league_ids).order_by('level', 'name'))


def finance_season_open(saison: str) -> dict:
    """Saisonstart-Job (idempotent via SeasonFinanceState.opened_at)."""
    from game.models import Club, SeasonFinanceState
    from .snapshot import ensure_season_snapshot
    from .sponsors import generate_offers
    from .tv import ensure_tv_pots

    saison = str(saison)
    state, _ = SeasonFinanceState.objects.get_or_create(saison=saison)
    if state.opened_at:
        return {'saison': saison, 'skipped': True}

    snapshot = ensure_season_snapshot(saison)
    pots = ensure_tv_pots(saison)

    offers_created, offer_errors = 0, []
    clubs = Club.objects.filter(league__isnull=False).select_related('league')
    for club in clubs:
        try:
            offers_created += len(generate_offers(club, saison))
        except Exception as exc:
            offer_errors.append(f'{club.name}: {exc}')
            logger.exception('Sponsorangebote für %s fehlgeschlagen', club)

    state.opened_at = timezone.now()
    state.save(update_fields=['opened_at'])

    return {
        'saison': saison,
        'skipped': False,
        'gehalts_anker': str(snapshot.gehalts_anker),
        'tv_pots': len(pots),
        'sponsor_offers': offers_created,
        'errors': offer_errors,
    }


def finance_season_close(saison: str) -> dict:
    """Saisonende-Job (idempotent; Teil-Läufe erlaubt, s. Moduldocstring)."""
    from game.models import CupSeason, SeasonFinanceState, SponsorOffer
    from .events import sync_cup_premiums
    from .sponsors import book_zieljaeger_bonus
    from .tv import distribute_season_tv, update_koeffizienten

    saison = str(saison)
    state, _ = SeasonFinanceState.objects.get_or_create(saison=saison)
    if state.closed_at:
        return {'saison': saison, 'skipped': True}

    report = {'saison': saison, 'skipped': False,
              'leagues': {}, 'cups': {}, 'zieljaeger': [], 'errors': []}

    # ── 1. TV-Saisonausschüttung je abgeschlossener Liga ─────────────────────
    ligen = _saison_ligen(saison)
    alle_komplett = bool(ligen)
    for league in ligen:
        if not _liga_ist_komplett(league, saison):
            alle_komplett = False
            report['leagues'][league.name] = 'offen — noch nicht ausgeschüttet'
            continue
        try:
            res = distribute_season_tv(league, saison)
            report['leagues'][league.name] = {
                'booked': len(res['booked']), 'skipped': len(res['skipped']),
            }
            report['errors'].extend(res['errors'])
        except Exception as exc:
            alle_komplett = False
            report['errors'].append(f'TV-Ausschüttung {league.name}: {exc}')
            logger.exception('TV-Ausschüttung für %s fehlgeschlagen', league)

    # ── 2. Pokalprämien-Backstop ─────────────────────────────────────────────
    for cup_season in CupSeason.objects.filter(season=saison):
        try:
            res = sync_cup_premiums(cup_season)
            report['cups'][str(cup_season)] = res['booked']
            report['errors'].extend(res['errors'])
        except Exception as exc:
            report['errors'].append(f'Pokalprämien {cup_season}: {exc}')
            logger.exception('Pokalprämien-Sync für %s fehlgeschlagen', cup_season)

    # ── 3. Zieljäger-Boni (V1: gewaehlt=True; V2: aktive Contracts) ──────────
    from .sponsors import book_zieljaeger_bonus_v2

    zieljaeger_offers = SponsorOffer.objects.filter(
        saison=saison, gewaehlt=True, typ=SponsorOffer.TYP_ZIELJAEGER,
    ).select_related('club')
    for offer in zieljaeger_offers:
        try:
            tx = book_zieljaeger_bonus(offer.club, saison)
            if tx is not None:
                report['zieljaeger'].append(f'{offer.club.name} (V1)')
        except Exception as exc:
            report['errors'].append(f'Zielbonus V1 {offer.club.name}: {exc}')

    clubs_v1 = {o.club_id for o in zieljaeger_offers}
    clubs_all = set(
        SponsorOffer.objects.filter(saison=saison)
        .values_list('club_id', flat=True).distinct()
    )
    from game.models import Club
    for club in Club.objects.filter(pk__in=clubs_all):
        try:
            txs = book_zieljaeger_bonus_v2(club, saison)
            if txs:
                report['zieljaeger'].append(f'{club.name} (V2, {len(txs)} Slots)')
        except Exception as exc:
            report['errors'].append(f'Zielbonus V2 {club.name}: {exc}')

    # ── 3b. Sponsor-Contracts auslaufen lassen (SPEC §9 sponsor_season_close) ──
    try:
        from .sponsors import expire_contracts_v2
        expired = expire_contracts_v2(saison)
        report['sponsor_contracts_abgelaufen'] = expired
    except Exception as exc:
        report['errors'].append(f'Sponsor-Contracts ablaufen lassen: {exc}')

    # ── 4./5. Nur beim endgültigen Abschluss ─────────────────────────────────
    if alle_komplett:
        try:
            report['koeffizienten'] = update_koeffizienten(saison)
        except Exception as exc:
            report['errors'].append(f'Koeffizienten-Update: {exc}')
            logger.exception('Koeffizienten-Update %s fehlgeschlagen', saison)

        if report['errors']:
            # Fehler beim Abschluss: closed_at offen lassen, damit ein
            # Wiederholungslauf die fehlenden (idempotenten) Buchungen
            # nachholen kann — sonst wären sie dauerhaft „eingefroren".
            report['hinweis'] = (
                'Abschluss mit Fehlern — closed_at bleibt offen '
                'für einen Wiederholungslauf.'
            )
        else:
            state.closed_at = timezone.now()
            state.report_json = report
            state.save(update_fields=['closed_at', 'report_json'])
    else:
        report['hinweis'] = (
            'Noch nicht alle Ligen durchgespielt — Teil-Lauf, '
            'closed_at bleibt offen.'
        )

    return report
