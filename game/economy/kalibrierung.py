"""Kalibrierung (Spec Kap. 16) — Live-Kennzahlen vs. Zielkorridore.

Phase 7 des Finanzsystems: stellt die Ledger-Aggregationen des Phase-5-
Monitorings (game.economy.monitoring) gegen die Referenzkorridore der
15-Saisons-Wirtschaftssimulation und benennt je Kennzahl den zuständigen
EconomyParameter-Regler. Reine Lese-Aggregationen — Anpassungen laufen
ausschließlich über die EconomyParameter-Tabelle (nie Code-Konstanten),
und zwar als bewusste Admin-Entscheidung (keine Selbstjustierung).

Status-Semantik je Kennzahl:
  · 'ok'            — Ist-Wert liegt im Zielkorridor
  · 'warn'          — außerhalb des Korridors, unterhalb der Alarmschwelle
  · 'alarm'         — Alarmschwelle laut Spec 12.5/16 gerissen
  · 'nicht_messbar' — Datenbasis reicht nicht (z. B. nur eine Saison,
                      laufende Saison, keine Transfers) — NIE stilles 'ok'.
"""
from decimal import Decimal
from statistics import median

from django.db.models import Sum

from . import monitoring
from .params import current_season

# ── Status-Konstanten ────────────────────────────────────────────────────
STATUS_OK = 'ok'
STATUS_WARN = 'warn'
STATUS_ALARM = 'alarm'
STATUS_NICHT_MESSBAR = 'nicht_messbar'

STATUS_LABELS = {
    STATUS_OK: 'Im Korridor',
    STATUS_WARN: 'Außerhalb Korridor',
    STATUS_ALARM: 'Alarm',
    STATUS_NICHT_MESSBAR: 'Nicht messbar',
}

# ── Zielkorridore (Spec Kap. 16 / 12.5) ─────────────────────────────────
GELDMENGE_DRIFT_TOLERANZ = 0.02      # Wachstum ≈ MW-Drift ± 2 Prozentpunkte
GEHALT_KORRIDOR_KLEIN = (0.16, 0.20)  # kleine Vereine: 16–20 % des Kader-MW
GEHALT_KORRIDOR_TOP = (0.28, 0.30)    # Topvereine: 28–30 % des Kader-MW
GEHALT_ALARM_ABSTAND = 0.10           # > 10 pp außerhalb → Alarm
ZUSCHAUER_PLAUSIBEL = (0.5, 1.3)      # Zuschauer ÷ min(Basisnachfrage, Kap.)
TOP_GRUPPE_ANTEIL = 0.25              # obere/untere 25 % nach Kader-MW


# ── Regler-Registry (Spec Kap. 16) ──────────────────────────────────────
# 'key' = EconomyParameter-Key (None = reine Admin-Empfehlung ohne Key).
# 'wirkt_auf' referenziert Kennzahl-IDs des Kalibrierungs-Reports.
# 'kalibrierung' = True markiert die offiziellen [KALIBRIERUNG]-Regler
# aus Spec Kap. 16; weitere Einträge sind Leitfaden-Verweise (welcher
# Regler wirkt auf welche Kennzahl), tragen aber kein Badge.
KALIBRIERUNG_REGLER = [
    {
        'key': 'BETRIEBSQUOTE',
        'kapitel': '10',
        'kalibrierung': True,
        'wirkt_auf': ['geldmenge'],
        'beschreibung': (
            'Wichtigster Geldmengen-Regler: Quote auf verbuchte Einnahmen '
            'als Betriebskosten-Senke. Höher = Geldmenge wächst langsamer. '
            'Simulationsbefund: ohne diese Senke > 40 % Wachstum/Saison.'
        ),
    },
    {
        'key': 'TV_TOEPFE',
        'kapitel': '7',
        'kalibrierung': True,
        'wirkt_auf': ['geldmenge'],
        'beschreibung': (
            'Absolute Höhe der TV-Ländertöpfe — größte einzelne '
            'Geldschöpfungsquelle. Senkt/hebt die Einnahmen aller Vereine '
            'proportional zur Liga-Verteilung.'
        ),
    },
    {
        'key': 'SPONSOR_MW_ANTEIL',
        'kapitel': '6',
        'kalibrierung': True,
        'wirkt_auf': ['geldmenge'],
        'beschreibung': (
            'Variabler Sponsoranteil am Kader-MW. Wirkt auf die '
            'Geldschöpfung großer Vereine überproportional (MW-abhängig).'
        ),
    },
    {
        'key': 'KI_ANGEBOTS_KADENZ',
        'kapitel': '9.3',
        'kalibrierung': True,
        'wirkt_auf': ['ki_anteil', 'abloese_mw'],
        'beschreibung': (
            'Angebots-Kadenz der KI-Käufer (offene Angebote, Angebote je '
            'Fenster, Cooldowns). Mehr Angebote = mehr Zirkulation und '
            'höherer KI-Anteil am Transfervolumen.'
        ),
    },
    {
        'key': 'KI_KAEUFER',
        'kapitel': '9.3',
        'kalibrierung': True,
        'wirkt_auf': ['ki_anteil', 'abloese_mw'],
        'beschreibung': (
            'Kauftyp-Schwellwerte (Lücken-Score, Qualität, Talent), '
            'Gebotsfaktoren und Governor-Limit der KI-Käufer. Achtung: '
            'enthält den operativen dry_run-Schalter der '
            'KI-Transferzentrale — der wird beim Speichern hier bewahrt.'
        ),
    },
    {
        'key': 'SCHMERZGRENZE_KONSTANTEN',
        'kapitel': '9',
        'kalibrierung': True,
        'wirkt_auf': ['abloese_mw'],
        'beschreibung': (
            'Verkäuferseite des Transfermarkts: Altersfaktoren, '
            'Realisierungswahrscheinlichkeit, Kernspieler-Zuschlag, '
            'Verkäufer-Margen. Bestimmt, wie weit Ablösen über dem MW '
            'liegen (Ziel-Median 1,3–1,8).'
        ),
    },
    {
        'key': None,
        'titel': 'Auktionsvolumen pro Saison',
        'kapitel': '12.4',
        'kalibrierung': True,
        'wirkt_auf': ['geldmenge'],
        'beschreibung': (
            'Bewusste Admin-Aufgabe ohne EconomyParameter-Key: Auktionen '
            'sind neben der BETRIEBSQUOTE die zweite große Geldsenke '
            '(in der 15-Saisons-Sim nicht modelliert — Restwachstum '
            '~7 %/Saison schließt sich über dosierte Auktionen). '
            'Empfehlung: bei Geldmengen-Alarm Auktionsvolumen erhöhen.'
        ),
    },
    # ── Leitfaden-Verweise ohne [KALIBRIERUNG]-Badge ────────────────────
    {
        'key': 'GEHALT_BASIS',
        'kapitel': '4',
        'kalibrierung': False,
        'wirkt_auf': ['gehaltslasten'],
        'beschreibung': (
            'Basisprozentsatz der log-progressiven Gehaltsformel. Hebt/'
            'senkt die Gehaltsquote ALLER Vereine gleichmäßig.'
        ),
    },
    {
        'key': 'GEHALT_PROGRESSION',
        'kapitel': '4',
        'kalibrierung': False,
        'wirkt_auf': ['gehaltslasten'],
        'beschreibung': (
            'Progressionsfaktor der Gehaltsformel: spreizt die Quote '
            'zwischen kleinen und Topvereinen (wirkt auf die Differenz '
            'der beiden Korridore).'
        ),
    },
    {
        'key': 'NACHFRAGE_KOEFF',
        'kapitel': '5',
        'kalibrierung': False,
        'wirkt_auf': ['zuschauer'],
        'beschreibung': (
            'Koeffizient der Basisnachfrage-Formel — skaliert die '
            'Zuschauernachfrage aller Vereine linear.'
        ),
    },
    {
        'key': 'NACHFRAGE_EXP',
        'kapitel': '5',
        'kalibrierung': False,
        'wirkt_auf': ['zuschauer'],
        'beschreibung': (
            'Exponent der Basisnachfrage-Formel — bestimmt, wie stark '
            'die Nachfrage mit dem Kader-MW wächst (Spreizung groß/klein).'
        ),
    },
    {
        'key': 'PREIS_ELASTIZITAET',
        'kapitel': '5',
        'kalibrierung': False,
        'wirkt_auf': ['zuschauer'],
        'beschreibung': (
            'Preiselastizität des Ticketpreisfaktors — wie stark '
            'Preisabweichungen vom Referenzpreis die Nachfrage bewegen.'
        ),
    },
]

# Offizielle [KALIBRIERUNG]-Keys (Spec Kap. 16) — für Badges & Tests.
KALIBRIERUNG_KEYS = frozenset(
    r['key'] for r in KALIBRIERUNG_REGLER
    if r['key'] and r.get('kalibrierung')
)


def regler_fuer(kennzahl_id: str) -> list[str]:
    """Namen der Regler, die auf eine Kennzahl wirken (für Report-Verweise)."""
    out = []
    for r in KALIBRIERUNG_REGLER:
        if kennzahl_id in r['wirkt_auf']:
            out.append(r['key'] or r.get('titel', ''))
    return out


# ── Kennzahl 1: Geldmengenwachstum vs. MW-Drift (±2 pp, Alarm > 4 %) ────

def mw_drift_verlauf() -> dict[str, float]:
    """MW-Drift je Saison aus der SeasonEconomySnapshot-Historie.

    Drift der Saison S = (Median[S+1] − Median[S]) / Median[S] — der
    Snapshot einer Saison entsteht bei Saisoneröffnung, die Differenz
    zweier Snapshots misst also die Drift der dazwischenliegenden Saison.
    Bewusst mw_median (roher Median), NICHT gehalts_anker (gedämpft).
    """
    from game.models import SeasonEconomySnapshot

    rows = [
        (s, mw) for s, mw in
        SeasonEconomySnapshot.objects.values_list('saison', 'mw_median')
        if (s or '').isdigit() and mw
    ]
    rows.sort(key=lambda t: int(t[0]))
    drift = {}
    for (s, mw), (_s2, mw2) in zip(rows, rows[1:]):
        if mw > 0:
            drift[s] = float((mw2 - mw) / mw)
    return drift


def geldmenge_vs_mw_drift(saison: str) -> dict:
    """Kennzahl: Geldmengenwachstum/Saison ≈ MW-Drift (±2 pp), Alarm > 4 %."""
    verlauf = monitoring.geldmengen_verlauf()
    row = next((v for v in verlauf if v['saison'] == str(saison)), None)
    wachstum = row['wachstum'] if row else None
    drift = mw_drift_verlauf().get(str(saison))

    hinweis = ''
    if wachstum is None:
        status = STATUS_NICHT_MESSBAR
        hinweis = ('Kein Geldmengenwachstum berechenbar '
                   '(keine Ledger-Basis für diese Saison).')
    elif wachstum > monitoring.ALARM_GELDMENGENWACHSTUM:
        status = STATUS_ALARM
        hinweis = 'Wachstum über der Alarmschwelle von 4 %/Saison.'
    elif drift is None:
        status = STATUS_NICHT_MESSBAR
        hinweis = ('MW-Drift braucht zwei Saison-Snapshots — '
                   'Korridorvergleich erst ab der zweiten Saison möglich.')
    elif abs(wachstum - drift) <= GELDMENGE_DRIFT_TOLERANZ:
        status = STATUS_OK
    else:
        status = STATUS_WARN
        hinweis = 'Wachstum weicht mehr als 2 pp von der MW-Drift ab.'

    return {
        'id': 'geldmenge',
        'titel': 'Geldmengenwachstum vs. MW-Drift',
        'korridor': 'Wachstum ≈ MW-Drift ± 2 pp · Alarm > 4 %/Saison',
        'status': status,
        'hinweis': hinweis,
        'regler': regler_fuer('geldmenge'),
        'wachstum': wachstum,
        'mw_drift': drift,
        'netto': row['netto'] if row else None,
    }


# ── Kennzahl 2: Ablöse/MW-Median (Ziel 1,3–1,8, Alarm > 2,2) ────────────

def abloese_mw(saison: str) -> dict:
    ratio = monitoring.abloese_mw_median(str(saison))
    med = ratio['median']
    lo, hi = monitoring.GESUND_ABLOESE_MW

    hinweis = ''
    if med is None:
        status = STATUS_NICHT_MESSBAR
        hinweis = 'Keine Transfers mit MW-Bezug in dieser Saison.'
    elif ratio['alarm']:
        status = STATUS_ALARM
        hinweis = 'Median über der Alarmschwelle 2,2 — Ablösen überhitzt.'
    elif ratio['gesund']:
        status = STATUS_OK
    else:
        status = STATUS_WARN
        hinweis = ('Median unter 1,3: Markt zahlt zu nah am MW.'
                   if med < lo else
                   'Median über 1,8: Ablösen laufen dem MW davon.')

    return {
        'id': 'abloese_mw',
        'titel': 'Ablöse/MW-Median',
        'korridor': f'Ziel {lo:.1f}–{hi:.1f} · Alarm > '
                    f'{monitoring.ALARM_ABLOESE_MW_MEDIAN:.1f}',
        'status': status,
        'hinweis': hinweis,
        'regler': regler_fuer('abloese_mw'),
        'median': med,
        'count': ratio['count'],
    }


# ── Kennzahl 3: Gehaltslasten nach Vereinsgröße ─────────────────────────

def _kader_mw_map() -> dict[int, Decimal]:
    """Kader-MW je Verein (aktueller Player.market_value — bewusste
    Approximation, identisch zu monitoring.abloese_mw_median)."""
    from game.models import Player

    rows = (
        Player.objects.filter(club__isnull=False)
        .values('club_id').annotate(s=Sum('market_value'))
    )
    return {r['club_id']: r['s'] or Decimal('0') for r in rows}


def gehaltslasten(saison: str) -> dict:
    """Kennzahl: Gehaltssumme (Ledger) ÷ Kader-MW, klein vs. top.

    Gruppen nach Kader-MW: obere 25 % = Topvereine, untere 25 % = kleine
    Vereine (Spec Kap. 16 spricht nur von „kleinen" vs. „Topvereinen").
    Laufende Saison: Gehälter sind erst anteilig gebucht — dann KEIN
    Korridorvergleich (nicht_messbar), Ist-Werte nur nachrichtlich.
    """
    from game.models import FinanceTransaction

    saison = str(saison)
    laufend = saison == current_season()

    gehalt = {
        r['club_id']: -(r['s'] or Decimal('0'))
        for r in FinanceTransaction.objects
        .filter(saison=saison, typ='GEHALT')
        .values('club_id').annotate(s=Sum('betrag'))
    }
    mw_map = _kader_mw_map()

    quoten = []   # (club_id, kader_mw, quote)
    for club_id, summe in gehalt.items():
        mw = mw_map.get(club_id) or Decimal('0')
        if mw > 0 and summe > 0:
            quoten.append((club_id, mw, float(summe / mw)))

    def _gruppen_median(rows):
        return median([q for _, _, q in rows]) if rows else None

    quote_klein = quote_top = None
    n_gruppe = 0
    if quoten:
        quoten.sort(key=lambda t: t[1])  # nach Kader-MW aufsteigend
        n_gruppe = max(1, int(len(quoten) * TOP_GRUPPE_ANTEIL))
        quote_klein = _gruppen_median(quoten[:n_gruppe])
        quote_top = _gruppen_median(quoten[-n_gruppe:])

    def _abstand(quote, korridor):
        lo, hi = korridor
        if quote is None:
            return None
        if quote < lo:
            return lo - quote
        if quote > hi:
            return quote - hi
        return 0.0

    hinweis = ''
    if not quoten:
        status = STATUS_NICHT_MESSBAR
        hinweis = 'Keine Gehaltsbuchungen mit Kader-MW-Basis in der Saison.'
    elif laufend:
        status = STATUS_NICHT_MESSBAR
        hinweis = ('Laufende Saison: Gehälter erst anteilig gebucht — '
                   'Korridorvergleich erst nach Saisonabschluss. '
                   'Ist-Werte nur nachrichtlich.')
    else:
        ab_klein = _abstand(quote_klein, GEHALT_KORRIDOR_KLEIN)
        ab_top = _abstand(quote_top, GEHALT_KORRIDOR_TOP)
        max_ab = max(a for a in (ab_klein, ab_top) if a is not None)
        if max_ab == 0.0:
            status = STATUS_OK
        elif max_ab > GEHALT_ALARM_ABSTAND:
            status = STATUS_ALARM
            hinweis = ('Gehaltsquote mehr als 10 pp außerhalb des '
                       'Korridors — Gehaltsformel-Regler prüfen.')
        else:
            status = STATUS_WARN
            hinweis = 'Gehaltsquote außerhalb des Zielkorridors.'

    return {
        'id': 'gehaltslasten',
        'titel': 'Gehaltslasten nach Vereinsgröße',
        'korridor': 'klein 16–20 % · top 28–30 % des Kader-MW',
        'status': status,
        'hinweis': hinweis,
        'regler': regler_fuer('gehaltslasten'),
        'quote_klein': quote_klein,
        'quote_top': quote_top,
        'clubs_gesamt': len(quoten),
        'gruppen_groesse': n_gruppe,
        'laufend': laufend,
    }


# ── Kennzahl 4: Zuschauer-Plausibilität ─────────────────────────────────

def zuschauer_plausibilitaet() -> dict:
    """Kennzahl: Zuschauer ÷ min(Basisnachfrage, Kapazität) je Heimspiel.

    Datenbasis: alle MatchdayRevenue-Zeilen (KEINE Saison-Zuordnung —
    das Modell trägt keine Saison, match_result ist nullable; daher
    bewusst globale Betrachtung über den gesamten Bestand).
    Plausibilitätsband 0,5–1,3 aus den Nachfragefaktor-Spannen
    (Beliebtheit 0,7–1,2 · Gegner 0,85–1,3 · Preis 0,5–1,3).
    Reine Plausibilität: ok/warn, kein Alarm.
    """
    from game.models import MatchdayRevenue

    from .sponsors import kader_marktwert
    from .stadium import basisnachfrage

    rows = list(
        MatchdayRevenue.objects.select_related('stadium__club')
    )

    basis_cache: dict[int, float] = {}
    ratios, auslastungen, ausreisser = [], [], []
    lo, hi = ZUSCHAUER_PLAUSIBEL
    for r in rows:
        stadium = r.stadium
        club = stadium.club
        if club is None or not r.attendance:
            continue
        if club.pk not in basis_cache:
            basis_cache[club.pk] = basisnachfrage(kader_marktwert(club))
        basis = basis_cache[club.pk]
        kapazitaet = float(
            (stadium.capacity_standing or 0)
            + (stadium.capacity_seating or 0)
            + (stadium.capacity_vip or 0)
        )
        referenz = min(basis, kapazitaet) if kapazitaet > 0 else basis
        if referenz <= 0:
            continue
        ratio = float(r.attendance) / referenz
        ratios.append(ratio)
        if r.auslastung_pct is not None:
            auslastungen.append(float(r.auslastung_pct))
        if not lo <= ratio <= hi:
            ausreisser.append({'club': club.name, 'ratio': ratio,
                               'attendance': r.attendance})

    hinweis = ''
    if not ratios:
        status = STATUS_NICHT_MESSBAR
        med = None
        hinweis = 'Keine Heimspiel-Einnahmezeilen mit Zuschauerdaten.'
    else:
        med = median(ratios)
        if lo <= med <= hi:
            status = STATUS_OK
        else:
            status = STATUS_WARN
            hinweis = ('Median unter dem Plausibilitätsband: Nachfrage- '
                       'oder Preisfaktoren drücken zu stark.'
                       if med < lo else
                       'Median über dem Plausibilitätsband: Basisnachfrage '
                       'unterschätzt die realen Zuschauer.')

    ausreisser.sort(key=lambda a: a['ratio'])
    return {
        'id': 'zuschauer',
        'titel': 'Zuschauer-Plausibilität',
        'korridor': f'Zuschauer ÷ Basisnachfrage {lo:.1f}–{hi:.1f} '
                    '(global, keine Saison-Zuordnung)',
        'status': status,
        'hinweis': hinweis,
        'regler': regler_fuer('zuschauer'),
        'median': med,
        'auslastung_median': median(auslastungen) if auslastungen else None,
        'spiele': len(ratios),
        'ausreisser': ausreisser[:10],
    }


# ── Kennzahl 5: KI-Kaufvolumen-Anteil ───────────────────────────────────

def ki_kaufvolumen(saison: str) -> dict:
    from .ai_buyer import governor_status

    g = governor_status(str(saison))
    hinweis = ''
    if not g['gesamt_volumen']:
        status = STATUS_NICHT_MESSBAR
        hinweis = 'Kein Transfervolumen in dieser Saison.'
    elif g['ueberschritten']:
        status = STATUS_ALARM
        hinweis = ('Governor-Limit überschritten — KI-Käufe dominieren '
                   'den Transfermarkt.')
    else:
        status = STATUS_OK

    return {
        'id': 'ki_anteil',
        'titel': 'KI-Kaufvolumen-Anteil',
        'korridor': f'≤ {float(g["limit"]):.0%} des Transfervolumens '
                    '(Governor)',
        'status': status,
        'hinweis': hinweis,
        'regler': regler_fuer('ki_anteil'),
        'anteil': float(g['anteil']),
        'limit': float(g['limit']),
        'ki_volumen': g['ki_volumen'],
        'gesamt_volumen': g['gesamt_volumen'],
    }


# ── Gesamt-Report ───────────────────────────────────────────────────────

def kalibrierungs_report(saison: str | None = None) -> dict:
    """Alle fünf Kennzahlen + Zählstände für die Kalibrierungs-Ansicht."""
    saison = str(saison) if saison is not None else current_season()
    kennzahlen = [
        geldmenge_vs_mw_drift(saison),
        abloese_mw(saison),
        gehaltslasten(saison),
        zuschauer_plausibilitaet(),
        ki_kaufvolumen(saison),
    ]
    return {
        'saison': saison,
        'kennzahlen': kennzahlen,
        'alarm_count': sum(1 for k in kennzahlen
                           if k['status'] == STATUS_ALARM),
        'warn_count': sum(1 for k in kennzahlen
                          if k['status'] == STATUS_WARN),
        'nicht_messbar_count': sum(1 for k in kennzahlen
                                   if k['status'] == STATUS_NICHT_MESSBAR),
    }
