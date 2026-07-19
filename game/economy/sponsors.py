"""Sponsorsystem (Spec Kap. 6) — Jahresangebote mit Präsidenten-Erwartung.

Sponsorwert (6.1):
    Sponsorwert = SPONSOR_SOCKEL(Liga-Ebene) + SPONSOR_MW_ANTEIL × KaderMW
                  + Platzbonus(Vorsaison)

Jahresangebote (6.2): 3–5 generierte Angebote je Saison, Laufzeit genau
1 Saison. Alle Angebote haben denselben Erwartungswert ≈ Sponsorwert —
kalibriert auf die Präsidenten-Erwartung (erwarteter Platz aus der
Kaderstärke, game.season_goals) — ± SPONSOR_STREUUNG Zufall pro Angebot.
Der Zufall ist deterministisch je (Verein, Saison) geseedet, damit
wiederholte Generierungsversuche identische Angebote ergäben.

Typen und Fixanteil (SPONSOR_TYP_SPLIT):
    Sicherheit  100 % fix
    Sieggeld    ~50 % fix + X €/Pflichtspielsieg
    Zieljäger   ~60 % fix + Bonus bei Erreichen des Präsidenten-Ziels
    Zuschauer   ~50 % fix + X €/Stadionbesucher (Liga-Heimspiele)

Buchung: Fixanteil in Spieltagsraten (matchday_run), variable Anteile
eventbasiert (Ligasieg im matchday_run, Pokalsieg im Pokal-Hook,
Besucher nach dem Ticket-Booking, Zielbonus bei Saisonende).

Auto-Pick: Trifft der Manager (bzw. ein KI-Verein) keine Wahl, wird beim
ersten Finanzlauf der Saison automatisch das Sicherheits-Angebot gewählt.
"""
import random
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from .params import get_param

EINHEIT_SIEG = 'sieg'
EINHEIT_BESUCHER = 'besucher'
EINHEIT_ZIEL = 'ziel'

# Fiktive Sponsornamen-Pools je Typ (deterministische Auswahl per Seed).
_NAMEN = {
    'sicherheit': ['NordBank Gruppe', 'Aurora Versicherung', 'Continentale Energie',
                   'ProSecura AG', 'Helvetia Kapital'],
    'sieggeld': ['VictoryBet Sports', 'Adrenalin Drinks', 'TurboOil Motorsport',
                 'Sprint Telekom', 'PowerPlay Media'],
    'zieljaeger': ['Zenith Automobile', 'Falcon Airways', 'Titan Industrie',
                   'Apex Consulting', 'Meridian Tech'],
    'zuschauer': ['StadionBräu Brauerei', 'FanFood Catering', 'Arena Mobility',
                  'CityTrans Verkehr', 'Tribüne Textil'],
}


# ── Sponsorwert (6.1) ────────────────────────────────────────────────────────

def kader_marktwert(club) -> Decimal:
    """Summe der Marktwerte aller Kaderspieler (NULL zählt nicht mit)."""
    from django.db.models import Sum
    from game.models import Player

    total = (
        Player.objects.filter(club=club)
        .aggregate(s=Sum('market_value'))['s']
    )
    return Decimal(total or 0)


def _liga_level_key(club) -> str:
    level = int(getattr(club.league, 'level', 1) or 1) if club.league_id else 2
    return 'liga1' if level <= 1 else 'liga2'


def _vorsaison_platz(club, saison: str) -> tuple[int, int]:
    """(Platz, Ligagröße) der Vorsaison; Fallback: projizierter Rang.

    Vor der ersten abgeschlossenen Saison existiert keine Vorsaison-
    Tabelle — dann gilt der Kaderstärke-Rang der Präsidenten-Erwartung.
    """
    from game.models import LeagueStandings

    if saison.lstrip('-').isdigit():
        vorsaison = str(int(saison) - 1)
        standing = (
            LeagueStandings.objects
            .filter(club=club, season=vorsaison, position__gt=0)
            .select_related('league')
            .first()
        )
        if standing is not None:
            n = LeagueStandings.objects.filter(
                league=standing.league, season=vorsaison,
            ).count()
            return standing.position, max(n, 2)

    from game.season_goals import project_goal_for_club
    p = project_goal_for_club(club)
    return p['rank_in_league'], max(p['league_size'], 2)


def platzbonus(club, saison: str) -> Decimal:
    """Platzbonus(Vorsaison): Maximalbonus für Platz 1, linear bis 0."""
    if not club.league_id:
        return Decimal('0.00')
    maximum = Decimal(str(get_param('SPONSOR_PLATZBONUS_MAX', saison)))
    platz, n = _vorsaison_platz(club, saison)
    anteil = Decimal(max(0, n - platz)) / Decimal(n - 1)
    return (maximum * anteil).quantize(Decimal('0.01'))


def sponsorwert(club, saison: str) -> Decimal:
    """Basis der Angebote (Spec 6.1) — ohne Fanbeliebtheit."""
    sockel = Decimal(str(get_param('SPONSOR_SOCKEL', saison)[_liga_level_key(club)]))
    mw_anteil = Decimal(str(get_param('SPONSOR_MW_ANTEIL', saison)))
    return (
        sockel + mw_anteil * kader_marktwert(club) + platzbonus(club, saison)
    ).quantize(Decimal('0.01'))


# ── Präsidenten-Erwartung (Kalibrierung der variablen Anteile) ───────────────

def _liga_spieltage(club, saison: str) -> tuple[int, int]:
    """(Spieltage gesamt, Heimspiele) aus dem Spielplan der Vereinsliga."""
    from .tv import league_clubs_and_matchdays

    if not club.league_id:
        return 34, 17
    club_ids, max_md = league_clubs_and_matchdays(club.league, saison)
    n = len(club_ids) or 18
    heimspiele = max(1, max_md // 2 if max_md > 1 else n - 1)
    return max(max_md, 1), heimspiele


def erwartete_siege(club, saison: str) -> Decimal:
    """Erwartete Ligasiege: Quote linear vom erwarteten Platz interpoliert.

    Bewusst NUR Ligaspiele (konservativ) — Pokalsiege zahlen zusätzlich
    aus, sind aber nicht in der Kalibrierung eingepreist.
    """
    from game.season_goals import project_goal_for_club

    quoten = get_param('SPONSOR_ERWARTETE_SIEGE', saison)
    top = Decimal(str(quoten['platz1']))
    bottom = Decimal(str(quoten['letzter']))

    p = project_goal_for_club(club)
    n = max(p['league_size'], 2)
    rang = min(max(p['rank_in_league'], 1), n)
    quote = top - (top - bottom) * Decimal(rang - 1) / Decimal(n - 1)

    spieltage, _ = _liga_spieltage(club, saison)
    return (quote * spieltage).quantize(Decimal('0.01'))


def erwartete_besucher(club, saison: str) -> Decimal:
    """Erwartete Saison-Gesamtbesucher der Liga-Heimspiele."""
    from game.stadium_revenue import calculate_auslastung

    try:
        stadium = club.stadium
    except Exception:
        return Decimal('0.00')

    kapazitaet = (
        stadium.capacity_standing + stadium.capacity_seating + stadium.capacity_vip
    )
    auslastung = calculate_auslastung(
        fan_popularity=club.fan_popularity,
        price_standing=float(stadium.price_standing),
        price_seating=float(stadium.price_seating),
        competition_factor=1.0,
        opponent_strength=65.0,
    )
    _, heimspiele = _liga_spieltage(club, saison)
    return (Decimal(kapazitaet) * Decimal(str(auslastung)) * heimspiele)\
        .quantize(Decimal('0.01'))


# ── Angebots-Generator (6.2) ─────────────────────────────────────────────────

def generate_offers(club, saison: str) -> list:
    """Erzeugt die 3–5 Jahresangebote eines Vereins (idempotent).

    Existieren bereits Angebote für (Verein, Saison), werden genau diese
    zurückgegeben. Das Sicherheits-Angebot ist immer dabei.
    """
    from game.models import SponsorOffer

    saison = str(saison)
    vorhandene = list(SponsorOffer.objects.filter(club=club, saison=saison))
    if vorhandene:
        return vorhandene

    rng = random.Random(f'sponsor:{club.pk}:{saison}')
    anzahl_cfg = get_param('SPONSOR_ANGEBOTE_ANZAHL', saison)
    anzahl = rng.randint(int(anzahl_cfg['min']), int(anzahl_cfg['max']))

    typen = ['sicherheit']
    andere = ['sieggeld', 'zieljaeger', 'zuschauer']
    rng.shuffle(andere)
    typen += andere[:max(0, anzahl - 1)]
    while len(typen) < anzahl:  # 5. Angebot: zufälliger Zweittyp
        typen.append(rng.choice(andere))

    wert = sponsorwert(club, saison)
    streuung = float(get_param('SPONSOR_STREUUNG', saison))
    splits = get_param('SPONSOR_TYP_SPLIT', saison)
    ziel_wkt = Decimal(str(get_param('SPONSOR_ZIEL_WAHRSCHEINLICHKEIT', saison)))

    e_siege = None
    e_besucher = None

    offers = []
    namen_verbraucht = set()
    for typ in typen:
        ew = (wert * Decimal(str(1 + rng.uniform(-streuung, streuung))))\
            .quantize(Decimal('0.01'))
        split = Decimal(str(splits[typ]))
        fix = (ew * split).quantize(Decimal('0.01'))
        var_ew = ew - fix

        variable = {}
        if typ == 'sieggeld':
            if e_siege is None:
                e_siege = erwartete_siege(club, saison)
            einzel = (var_ew / e_siege).quantize(Decimal('0.01')) \
                if e_siege > 0 else Decimal('0.00')
            variable = {
                'einheit': EINHEIT_SIEG,
                'betrag': str(einzel),
                'erwartete_events': str(e_siege),
            }
        elif typ == 'zuschauer':
            if e_besucher is None:
                e_besucher = erwartete_besucher(club, saison)
            einzel = (var_ew / e_besucher).quantize(Decimal('0.0001')) \
                if e_besucher > 0 else Decimal('0.0000')
            variable = {
                'einheit': EINHEIT_BESUCHER,
                'betrag': str(einzel),
                'erwartete_events': str(e_besucher),
            }
        elif typ == 'zieljaeger':
            bonus = (var_ew / ziel_wkt).quantize(Decimal('0.01')) \
                if ziel_wkt > 0 else Decimal('0.00')
            from game.season_goals import project_goal_for_club
            p = project_goal_for_club(club)
            variable = {
                'einheit': EINHEIT_ZIEL,
                'betrag': str(bonus),
                'erwartete_events': str(ziel_wkt),
                'ziel_label': p['goal_tier_label'],
            }

        pool = [n for n in _NAMEN[typ] if n not in namen_verbraucht] or _NAMEN[typ]
        name = rng.choice(pool)
        namen_verbraucht.add(name)

        offers.append(SponsorOffer(
            club=club, saison=saison, typ=typ, sponsor_name=name,
            fix_betrag=fix, variable_json=variable, erwartungswert=ew,
        ))

    from game.models import SponsorOffer as _SO
    _SO.objects.bulk_create(offers)
    return list(_SO.objects.filter(club=club, saison=saison))


# ── Auswahl ──────────────────────────────────────────────────────────────────

class SponsorChoiceError(Exception):
    """Ungültige Sponsor-Wahl (bereits gewählt / falsche Saison)."""


def choose_offer(offer) -> None:
    """Markiert ein Angebot als gewählt — bindend für die ganze Saison."""
    from game.models import SponsorOffer

    try:
        with transaction.atomic():
            locked = SponsorOffer.objects.select_for_update().get(pk=offer.pk)
            if locked.gewaehlt:
                return
            if SponsorOffer.objects.filter(
                club=locked.club, saison=locked.saison, gewaehlt=True,
            ).exclude(pk=locked.pk).exists():
                raise SponsorChoiceError(
                    'Für diese Saison wurde bereits ein Sponsor gewählt — '
                    'der Vertrag läuft die ganze Saison.'
                )
            locked.gewaehlt = True
            locked.angenommen_at = timezone.now()
            locked.save(update_fields=['gewaehlt', 'angenommen_at'])
    except IntegrityError:
        # Race zweier gleichzeitiger Wahlen auf VERSCHIEDENE Angebote:
        # Beide passieren den exists()-Check, der DB-Partial-Unique-
        # Constraint lehnt die zweite ab — freundlich melden statt 500.
        raise SponsorChoiceError(
            'Für diese Saison wurde bereits ein Sponsor gewählt — '
            'der Vertrag läuft die ganze Saison.'
        )
    offer.gewaehlt = True
    offer.angenommen_at = locked.angenommen_at


def get_active_offer(club, saison: str, autopick: bool = True):
    """Gewähltes Angebot des Vereins — mit Lazy-Generierung und Auto-Pick.

    autopick=True (Finanzlauf): Ohne Wahl wird automatisch das
    Sicherheits-Angebot angenommen (Spec-Verhalten für KI-Vereine und
    zögerliche Manager). autopick=False (UI): None, solange nichts
    gewählt wurde.
    """
    from game.models import SponsorOffer

    saison = str(saison)
    chosen = SponsorOffer.objects.filter(
        club=club, saison=saison, gewaehlt=True,
    ).first()
    if chosen or not autopick:
        return chosen

    offers = generate_offers(club, saison)
    sicherheit = next(
        (o for o in offers if o.typ == 'sicherheit'), offers[0] if offers else None,
    )
    if sicherheit is None:
        return None
    try:
        choose_offer(sicherheit)
    except SponsorChoiceError:
        return SponsorOffer.objects.filter(
            club=club, saison=saison, gewaehlt=True,
        ).first()
    return sicherheit


# ── Buchungspfade ────────────────────────────────────────────────────────────

def sponsor_fix_rate(offer, saison: str) -> Decimal:
    """Fixanteil je Spieltag (Spieltagsraten wie der TV-Sockel)."""
    spieltage, _ = _liga_spieltage(offer.club, saison)
    return (Decimal(offer.fix_betrag) / spieltage).quantize(Decimal('0.01'))


def _variable(offer) -> tuple[str | None, Decimal]:
    v = offer.variable_json or {}
    einheit = v.get('einheit')
    try:
        betrag = Decimal(str(v.get('betrag', '0')))
    except Exception:
        betrag = Decimal('0')
    return einheit, betrag


def book_sieg_bonus(club, offer, saison: str, *, beschreibung: str,
                    referenz_typ: str, referenz_id: int | None,
                    spieltag: int | None = None):
    """Sieggeld-Bonus für EINEN Pflichtspielsieg (idempotent je Referenz)."""
    from game.models import FinanceTransaction
    from .booking import book

    einheit, betrag = _variable(offer)
    if einheit != EINHEIT_SIEG or betrag <= 0:
        return None
    if FinanceTransaction.objects.filter(
        club=club, typ='SPONSOR_VARIABEL',
        referenz_typ=referenz_typ, referenz_id=referenz_id,
    ).exists():
        return None
    return book(
        club, 'SPONSOR_VARIABEL', betrag,
        beschreibung=beschreibung[:200],
        saison=saison, spieltag=spieltag,
        referenz_typ=referenz_typ, referenz_id=referenz_id,
        pflicht=True,
    )


def book_zuschauer_bonus(club, offer, attendance: int, saison: str,
                         spieltag: int | None = None):
    """Zuschauer-Bonus für EIN Liga-Heimspiel (Aufruf aus matchday_run —
    dort durch den FinanceMatchdayRun-Marker bereits idempotent)."""
    from .booking import book

    einheit, betrag = _variable(offer)
    if einheit != EINHEIT_BESUCHER or betrag <= 0 or attendance <= 0:
        return None
    summe = (betrag * attendance).quantize(Decimal('0.01'))
    if summe <= 0:
        return None
    return book(
        club, 'SPONSOR_VARIABEL', summe,
        beschreibung=(
            f'{offer.sponsor_name}: Zuschauerbonus '
            f'({attendance:,} Besucher)'.replace(',', '.')
        )[:200],
        saison=saison, spieltag=spieltag,
        referenz_typ='sponsor_zuschauer', referenz_id=offer.pk,
        pflicht=True,
    )


def book_zieljaeger_bonus(club, saison: str):
    """Zielbonus bei Saisonende, wenn das Präsidenten-Ziel erreicht wurde.

    Idempotent je (Verein, Saison). Voraussetzung: SeasonGoal wurde
    bereits ausgewertet (achieved=True).
    """
    from game.models import FinanceTransaction, SeasonGoal, SponsorOffer
    from .booking import book

    saison = str(saison)
    offer = SponsorOffer.objects.filter(
        club=club, saison=saison, gewaehlt=True, typ='zieljaeger',
    ).first()
    if offer is None:
        return None

    einheit, betrag = _variable(offer)
    if einheit != EINHEIT_ZIEL or betrag <= 0:
        return None

    if not saison.lstrip('-').isdigit():
        return None
    goal = SeasonGoal.objects.filter(
        club=club, season_number=int(saison), achieved=True,
    ).first()
    if goal is None:
        return None

    if FinanceTransaction.objects.filter(
        club=club, saison=saison, typ='SPONSOR_VARIABEL',
        referenz_typ='sponsor_ziel', referenz_id=offer.pk,
    ).exists():
        return None

    ziel_label = (offer.variable_json or {}).get('ziel_label', 'Saisonziel')
    return book(
        club, 'SPONSOR_VARIABEL', betrag,
        beschreibung=f'{offer.sponsor_name}: Zielbonus ({ziel_label} erreicht)'[:200],
        saison=saison,
        referenz_typ='sponsor_ziel', referenz_id=offer.pk,
        pflicht=True,
    )
