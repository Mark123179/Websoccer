"""TV-/Ligagelder & Ligakoeffizient (Spec Kap. 7).

Landeskoeffizient (7.1): 5-Jahreswertung pro Land aus LandKoeffizient-
Zeilen (Fenster: aktuelle Saison und die 4 davor, numerisch). Der Rang
bestimmt die Topfgröße (TV_TOEPFE). Beim Launch geseedet mit realen
UEFA-Werten (Migration 0123) — eine Seed-Zeile = komplette 5-Jahres-Summe.

TVPot (7.2): Bei finance_season_open (oder lazy beim ersten Zugriff)
wird der Ländertopf je Land für die Saison EINGEFROREN — der Rang bleibt
saisonstabil.

Verteilung (7.3): 50 % Sockel (Spieltagsraten, matchday_run) +
30 % Platzierung + 20 % Vereins-5-Jahreswertung, beide linear degressiv,
Ausschüttung bei Saisonende (distribute_season_tv). Ergibt Spreizung
Platz 1 : letzter ≈ 2,6×.

Auf-/Abstieg (7.4): book_fallschirm() als Servicepfad — es existiert
noch keine Auf-/Abstiegsmechanik, daher kein automatischer Hook.

Koeffizienten-Update: update_koeffizienten() ist ein dokumentierter
Carry-Forward-STUB, solange keine Europapokal-Simulation existiert:
Die neue Saisonzeile erhält 1/5 der bisherigen Fenstersumme, damit die
5-Jahres-Summen (und damit die Ränge) stabil bleiben. Sobald echte
Europapokal-Ergebnisse simuliert werden, ersetzt das Punkteschema
(analog UEFA) diesen Stub.
"""
from decimal import Decimal

from django.db import transaction

from .params import get_param

KOEFF_FENSTER = 5


# ── Koeffizienten ────────────────────────────────────────────────────────────

def _fenster_saisons(saison: str) -> list[str] | None:
    """Saison-Strings des 5-Jahres-Fensters (None bei nicht-numerischer Saison)."""
    s = str(saison).strip()
    if not s.lstrip('-').isdigit():
        return None
    target = int(s)
    return [str(n) for n in range(target - KOEFF_FENSTER + 1, target + 1)]


def land_koeff_summen(saison: str) -> dict[str, Decimal]:
    """5-Jahres-Summe je Land (Fenster endet in der angegebenen Saison)."""
    from game.models import LandKoeffizient

    qs = LandKoeffizient.objects.all()
    fenster = _fenster_saisons(saison)
    if fenster is not None:
        qs = qs.filter(saison__in=fenster)

    summen: dict[str, Decimal] = {}
    for land, punkte in qs.values_list('land', 'punkte'):
        summen[land] = summen.get(land, Decimal('0')) + punkte
    return summen


def land_rank_map(saison: str) -> dict[str, int]:
    """Koeffizienten-Rang je Land (1 = höchste 5-Jahres-Summe)."""
    summen = land_koeff_summen(saison)
    geordnet = sorted(summen.items(), key=lambda t: (-t[1], t[0]))
    return {land: idx + 1 for idx, (land, _pkt) in enumerate(geordnet)}


def verein_koeff_summen(club_ids, saison: str) -> dict[int, Decimal]:
    """5-Jahres-Summe je Verein (fehlende Vereine → 0 Punkte)."""
    from game.models import VereinKoeffizient

    qs = VereinKoeffizient.objects.filter(club_id__in=list(club_ids))
    fenster = _fenster_saisons(saison)
    if fenster is not None:
        qs = qs.filter(saison__in=fenster)

    summen = {cid: Decimal('0') for cid in club_ids}
    for cid, punkte in qs.values_list('club_id', 'punkte'):
        summen[cid] = summen.get(cid, Decimal('0')) + punkte
    return summen


# ── Ländertöpfe ──────────────────────────────────────────────────────────────

def _topf_fuer_rang(rang: int, saison: str) -> Decimal:
    """Gesamttopf laut TV_TOEPFE; Ränge jenseits der Tabelle → kleinster Topf."""
    toepfe = get_param('TV_TOEPFE', saison)
    if str(rang) in toepfe:
        return Decimal(str(toepfe[str(rang)]))
    max_rang = max(int(k) for k in toepfe)
    return Decimal(str(toepfe[str(max_rang)]))


def ensure_tv_pots(saison: str) -> dict[str, 'object']:
    """Friert die Ländertöpfe der Saison ein (idempotent).

    Rückgabe: {Land: TVPot}. Existieren bereits TVPot-Zeilen für die
    Saison, werden genau diese zurückgegeben (kein Neu-Ranking).
    """
    from game.models import TVPot

    saison = str(saison)
    vorhanden = {p.land: p for p in TVPot.objects.filter(saison=saison)}
    if vorhanden:
        return vorhanden

    pots = {}
    for land, rang in land_rank_map(saison).items():
        pot, _ = TVPot.objects.get_or_create(
            saison=saison, land=land,
            defaults={'rang': rang, 'gesamt': _topf_fuer_rang(rang, saison)},
        )
        pots[land] = pot
    return pots


def tv_pot_gesamt(land: str, saison: str) -> Decimal:
    """Gesamttopf eines Landes für die Saison (friert bei Bedarf lazy ein).

    Länder ohne Koeffizienten-Zeile erhalten den kleinsten Topf der
    TV_TOEPFE-Tabelle (Rang = Tabellenende).
    """
    pots = ensure_tv_pots(saison)
    if land in pots:
        return Decimal(pots[land].gesamt)

    toepfe = get_param('TV_TOEPFE', saison)
    max_rang = max(int(k) for k in toepfe)
    return Decimal(str(toepfe[str(max_rang)]))


def liga_topf(league, saison: str) -> Decimal:
    """Anteil der Liga am Landestopf (TV_SPLIT_LIGA nach League.level)."""
    gesamt = tv_pot_gesamt(league.country, saison)
    split = get_param('TV_SPLIT_LIGA', saison)
    key = 'liga1' if int(getattr(league, 'level', 1) or 1) <= 1 else 'liga2'
    return (gesamt * Decimal(str(split[key]))).quantize(Decimal('0.01'))


def league_clubs_and_matchdays(league, saison: str) -> tuple[set, int]:
    """(Club-IDs, maximaler Spieltag) aus dem Spielplan der Liga."""
    from game.models import SeasonFixture

    fixtures = SeasonFixture.objects.filter(league=league, season=str(saison))
    club_ids = set(fixtures.values_list('home_club_id', flat=True))
    max_md = (
        fixtures.order_by('-matchday').values_list('matchday', flat=True).first()
        or 1
    )
    return club_ids, max_md


def tv_sockel_rate(league, saison: str) -> Decimal:
    """TV-Sockel-Rate je Verein und Spieltag (50 %-Anteil in Raten)."""
    topf = liga_topf(league, saison)
    sockel_anteil = Decimal(str(get_param('TV_VERTEILUNG', saison)['sockel']))
    club_ids, max_md = league_clubs_and_matchdays(league, saison)
    n_clubs = len(club_ids) or 1
    return (topf * sockel_anteil / n_clubs / max_md).quantize(Decimal('0.01'))


# ── Saisonabschluss: Platz- und Koeffanteil ─────────────────────────────────

REFERENZ_SAISONABSCHLUSS = 'tv_saisonabschluss'


def _linear_degressiv(summe: Decimal, n: int) -> list[Decimal]:
    """Anteile für Rang 1..n, linear degressiv (Gewicht n, n-1, …, 1)."""
    gewicht_summe = n * (n + 1) // 2
    return [
        (summe * (n - rang + 1) / gewicht_summe).quantize(Decimal('0.01'))
        for rang in range(1, n + 1)
    ]


def distribute_season_tv(league, saison: str) -> dict:
    """Schüttet Platz- (30 %) und Koeffanteil (20 %) bei Saisonende aus.

    Idempotent je Verein: Existiert bereits eine TV_PLATZ-Buchung mit
    referenz_typ='tv_saisonabschluss' für (Verein, Saison), wird der
    Verein übersprungen.
    """
    from game.models import FinanceTransaction, LeagueStandings
    from .booking import book

    saison = str(saison)
    verteilung = get_param('TV_VERTEILUNG', saison)
    topf = liga_topf(league, saison)
    platz_summe = topf * Decimal(str(verteilung['platz']))
    koeff_summe = topf * Decimal(str(verteilung['koeff']))

    standings = list(
        LeagueStandings.objects
        .filter(league=league, season=saison)
        .select_related('club')
        .order_by('position', '-points', 'club__name')
    )
    if not standings:
        return {'booked': [], 'skipped': [], 'errors': ['Keine Tabelle vorhanden.']}

    n = len(standings)
    platz_anteile = _linear_degressiv(platz_summe, n)

    clubs = [s.club for s in standings]
    koeff = verein_koeff_summen([c.pk for c in clubs], saison)
    koeff_ranking = sorted(clubs, key=lambda c: (-koeff.get(c.pk, Decimal('0')), c.name))
    koeff_anteile = _linear_degressiv(koeff_summe, n)
    koeff_betrag = {
        club.pk: koeff_anteile[idx] for idx, club in enumerate(koeff_ranking)
    }

    schon_gebucht = set(
        FinanceTransaction.objects.filter(
            club_id__in=[c.pk for c in clubs],
            saison=saison, typ='TV_PLATZ',
            referenz_typ=REFERENZ_SAISONABSCHLUSS,
        ).values_list('club_id', flat=True)
    )

    _, max_md = league_clubs_and_matchdays(league, saison)
    booked, skipped, errors = [], [], []
    for idx, standing in enumerate(standings):
        club = standing.club
        if club.pk in schon_gebucht:
            skipped.append(club.name)
            continue
        try:
            # Beide Buchungen atomar: Der Skip-Guard prüft nur TV_PLATZ —
            # ohne Atomik könnte ein TV_KOEFF-Fehler den Anteil dauerhaft
            # verlieren (Wiederholung würde den Verein überspringen).
            with transaction.atomic():
                book(
                    club, 'TV_PLATZ', platz_anteile[idx],
                    beschreibung=f'TV-Gelder Platzierungsanteil (Platz {standing.position})',
                    saison=saison, spieltag=max_md,
                    referenz_typ=REFERENZ_SAISONABSCHLUSS, referenz_id=league.pk,
                    pflicht=True,
                )
                book(
                    club, 'TV_KOEFF', koeff_betrag[club.pk],
                    beschreibung='TV-Gelder Koeffizientenanteil (5-Jahreswertung)',
                    saison=saison, spieltag=max_md,
                    referenz_typ=REFERENZ_SAISONABSCHLUSS, referenz_id=league.pk,
                    pflicht=True,
                )
            booked.append(club.name)
        except Exception as exc:  # Ein Vereinsfehler stoppt nicht die Liga.
            errors.append(f'{club.name}: {exc}')

    return {'booked': booked, 'skipped': skipped, 'errors': errors}


# ── Fallschirm (7.4) ─────────────────────────────────────────────────────────

TV_TYPEN = ('TV_SOCKEL', 'TV_PLATZ', 'TV_KOEFF')


def book_fallschirm(club, saison: str, vorsaison: str | None = None):
    """Bucht die einmalige Fallschirmzahlung eines Absteigers.

    Betrag = FALLSCHIRM_QUOTE × TV-Gesamtsumme der Vorsaison. Servicepfad:
    Es existiert noch keine Auf-/Abstiegsmechanik, der Aufruf erfolgt
    manuell bzw. aus einer künftigen Abstiegs-Pipeline. Idempotent je
    (Verein, Saison).
    """
    from django.db.models import Sum
    from game.models import FinanceTransaction
    from .booking import book

    saison = str(saison)
    if vorsaison is None:
        if not saison.lstrip('-').isdigit():
            raise ValueError('Vorsaison nicht bestimmbar — bitte explizit angeben.')
        vorsaison = str(int(saison) - 1)

    if FinanceTransaction.objects.filter(
        club=club, saison=saison, typ='FALLSCHIRM',
    ).exists():
        return None

    letzte_tv = (
        FinanceTransaction.objects.filter(
            club=club, saison=vorsaison, typ__in=TV_TYPEN, betrag__gt=0,
        ).aggregate(s=Sum('betrag'))['s']
        or Decimal('0.00')
    )
    if letzte_tv <= 0:
        return None

    quote = Decimal(str(get_param('FALLSCHIRM_QUOTE', saison)))
    betrag = (quote * letzte_tv).quantize(Decimal('0.01'))
    return book(
        club, 'FALLSCHIRM', betrag,
        beschreibung=f'Fallschirmzahlung nach Abstieg (Saison {vorsaison})',
        saison=saison,
        referenz_typ='fallschirm', referenz_id=club.pk,
        pflicht=True,
    )


# ── Koeffizienten-Update (Carry-Forward-Stub) ────────────────────────────────

def update_koeffizienten(saison: str) -> dict:
    """Schreibt Koeffizienten-Zeilen für die Folgesaison (Carry-Forward-STUB).

    Solange keine Europapokal-Simulation existiert, erhält jedes Land /
    jeder Verein für die Folgesaison 1/5 seiner aktuellen Fenstersumme —
    die 5-Jahres-Summen und damit die Ränge bleiben stabil. Idempotent:
    vorhandene Zeilen der Folgesaison werden nie überschrieben.
    """
    from game.models import LandKoeffizient, VereinKoeffizient

    saison = str(saison)
    if not saison.lstrip('-').isdigit():
        return {'laender': 0, 'vereine': 0, 'skipped': True}
    folge = str(int(saison) + 1)

    laender = 0
    for land, summe in land_koeff_summen(saison).items():
        _, created = LandKoeffizient.objects.get_or_create(
            land=land, saison=folge,
            defaults={'punkte': (summe / KOEFF_FENSTER).quantize(Decimal('0.001'))},
        )
        laender += int(created)

    club_ids = list(
        VereinKoeffizient.objects.values_list('club_id', flat=True).distinct()
    )
    vereine = 0
    for cid, summe in verein_koeff_summen(club_ids, saison).items():
        if summe <= 0:
            continue
        _, created = VereinKoeffizient.objects.get_or_create(
            club_id=cid, saison=folge,
            defaults={'punkte': (summe / KOEFF_FENSTER).quantize(Decimal('0.001'))},
        )
        vereine += int(created)

    return {'laender': laender, 'vereine': vereine, 'skipped': False}
