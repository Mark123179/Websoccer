"""Ledger-Integritätsprüfung (Spec Kap. 12.1 / 15).

Der Kontostand (Club.budget) ist nur ein Performance-Cache — die Wahrheit
ist die Summe des Ledgers. Dieser Check vergleicht beide je Verein und
meldet Abweichungen (Admin-Alarm; Exit-Code ≠ 0 im Management-Command).
"""
from decimal import Decimal


def check_ledger_integrity(fix: bool = False) -> dict:
    """Vergleicht Ledger-Summe vs. Club.budget für alle Vereine.

    Args:
        fix: True = Konto-Cache aus dem Ledger neu setzen (Reparatur).

    Returns:
        {'checked': int, 'mismatches': [{'club', 'club_id', 'budget',
         'ledger', 'diff'}, ...], 'fixed': int}
    """
    from django.db.models import Sum
    from game.models import Club, FinanceTransaction

    ledger_sums = dict(
        FinanceTransaction.objects
        .values_list('club_id')
        .annotate(s=Sum('betrag'))
        .values_list('club_id', 's')
    )

    mismatches = []
    fixed = 0
    clubs = list(Club.objects.all().only('id', 'name', 'budget'))
    for club in clubs:
        ledger = ledger_sums.get(club.pk, Decimal('0.00')) or Decimal('0.00')
        budget = club.budget if club.budget is not None else Decimal('0.00')
        diff = (budget - ledger).quantize(Decimal('0.01'))
        if diff != 0:
            mismatches.append({
                'club': club.name,
                'club_id': club.pk,
                'budget': budget,
                'ledger': ledger,
                'diff': diff,
            })
            if fix:
                Club.objects.filter(pk=club.pk).update(budget=ledger)
                fixed += 1

    return {'checked': len(clubs), 'mismatches': mismatches, 'fixed': fixed}


# ── Vollständigkeitsprüfung (Typ-Marker je Spieltag+Verein) ──────────────────


def check_finance_completeness(
    saison: str | None = None,
    liga_id: int | None = None,
    spieltag: int | None = None,
) -> dict:
    """Prüft, ob alle simulierten Spieltage vollständige Finanz-Marker haben.

    Ein Spieltag gilt als "simuliert" wenn SeasonFixture-Zeilen für ihn
    existieren und is_played=True gesetzt ist. Pro Verein müssen dann alle
    Pflicht-Marker im FinanceMatchdayRun vorhanden sein (plus Haupt-Marker).

    Der Check ist read-only und idempotent — er bucht nichts.

    Erwartungs-Matrix (Spec Kap. 15):
      Alle Vereine (Heim + Auswärts): TV_SOCKEL, SPONSOR, GEHALT, STADION, BETRIEB.
      Nur Heimvereine zusätzlich:     TICKET.

    Hinweis zu STADION_SPIELTAG: wird als Teil des STADION-Markers abgedeckt
    (ein Marker für Unterhalt + Spieltagskosten); kein separater Check nötig.

    Args:
        saison:    Saisonfilter (z.B. '0'); None = alle Saisons.
        liga_id:   Primärschlüssel der Liga; None = alle Ligen.
        spieltag:  Spieltagfilter (1-basiert); None = alle Spieltage.

    Returns:
        {
          'gaps': [
            { 'liga': str, 'liga_id': int, 'saison': str,
              'spieltag': int, 'club': str, 'club_id': int,
              'missing': [str, ...],   # Marker-Typen die fehlen
              'no_header': bool,       # True = kein Header-Marker vorhanden
              'is_home': bool,         # True = Heimverein dieses Spieltags
            }, ...
          ],
          'checked_clubs': int,   # Anzahl geprüfter (Spieltag, Verein)-Kombinationen
        }
    """
    from django.db.models import Q

    from game.economy.matchday_run import (
        RUN_TYP_BETRIEB, RUN_TYP_GEHALT, RUN_TYP_HEADER,
        RUN_TYP_SPONSOR, RUN_TYP_STADION, RUN_TYP_TICKET, RUN_TYP_TV,
    )
    from game.models import FinanceMatchdayRun, SeasonFixture

    # Pflicht-Marker-Sets (Spec Kap. 15 / task #763):
    # Alle Vereine: TV_SOCKEL, SPONSOR, GEHALT, STADION, BETRIEB.
    # Heim-Verein zusätzlich: TICKET (bucht Einnahmen + Umfeld).
    PFLICHT_ALLE = frozenset({
        RUN_TYP_TV, RUN_TYP_SPONSOR, RUN_TYP_GEHALT,
        RUN_TYP_STADION, RUN_TYP_BETRIEB,
    })
    PFLICHT_HEIM = PFLICHT_ALLE | {RUN_TYP_TICKET}

    # ── Alle gespielten Fixtures laden (Filter anwenden) ───────────────────
    qs = SeasonFixture.objects.filter(is_played=True).select_related(
        'league', 'home_club', 'away_club',
    )
    if saison is not None:
        qs = qs.filter(season=str(saison))
    if liga_id is not None:
        qs = qs.filter(league_id=liga_id)
    if spieltag is not None:
        qs = qs.filter(matchday=spieltag)

    # ── Datenstruktur aufbauen ─────────────────────────────────────────────
    # spieltage: key=(liga_id, liga_name, saison, matchday)
    #            value={club_id: (club_obj, is_home)}
    spieltage: dict[tuple, dict[int, tuple]] = {}
    for f in qs.iterator():
        key = (f.league_id, f.league.name, str(f.season), f.matchday)
        slot = spieltage.setdefault(key, {})
        slot[f.home_club_id] = (f.home_club, True)
        slot[f.away_club_id] = (f.away_club, False)

    if not spieltage:
        return {'gaps': [], 'checked_clubs': 0}

    # ── Alle relevanten Marker in einer Batch-Query laden ─────────────────
    # Filter: je Spieltag-Saison-Kombination die beteiligten Club-IDs.
    q = Q()
    for (liga_id_, liga_name, saison_key, matchday_key), slot in spieltage.items():
        q |= Q(
            saison=saison_key,
            spieltag=matchday_key,
            club_id__in=list(slot.keys()),
        )

    # vorhandene: {(club_id, saison, spieltag): set(typen)}
    vorhandene: dict[tuple, set] = {}
    for club_id, sais, stag, typ in (
        FinanceMatchdayRun.objects.filter(q)
        .values_list('club_id', 'saison', 'spieltag', 'typ')
    ):
        vorhandene.setdefault((club_id, sais, stag), set()).add(typ)

    # ── Lücken erkennen ────────────────────────────────────────────────────
    gaps = []
    checked = 0
    for (liga_id_, liga_name, saison_key, matchday_key), slot in sorted(spieltage.items()):
        for club_id, (club, is_home) in sorted(slot.items(), key=lambda kv: kv[1][0].name):
            checked += 1
            marker_typen = vorhandene.get((club_id, saison_key, matchday_key), set())
            no_header = RUN_TYP_HEADER not in marker_typen
            schritt_marker = marker_typen - {RUN_TYP_HEADER}
            pflicht = PFLICHT_HEIM if is_home else PFLICHT_ALLE
            missing = sorted(pflicht - schritt_marker)

            if no_header or missing:
                gaps.append({
                    'liga': liga_name,
                    'liga_id': liga_id_,
                    'saison': saison_key,
                    'spieltag': matchday_key,
                    'club': club.name,
                    'club_id': club_id,
                    'missing': missing,
                    'no_header': no_header,
                    'is_home': is_home,
                })

    return {'gaps': gaps, 'checked_clubs': checked}
