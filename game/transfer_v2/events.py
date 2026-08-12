"""Gemeinsame Ereignis-Schicht des Transfersystems v2 (Master-Spec §5.7/§6).

Ein Vorgang (Listing, Gebot, Anfrage, Transfer, Leihe) meldet hier genau
EIN Ereignis. Aus derselben Ereignis-Quelle speisen sich

    * die Gerüchte-Engine (RumorNews + Vereinsnews-Karte, würfelbasiert),
    * der Push-Katalog (Benachrichtigungen an betroffene Manager) und
    * der Transfer-Ticker (Laufband auf dem Transfermarkt).

Alle Auslöser sind bewusst NEBENwirkungs-isoliert: schlägt die Gerüchte-
oder Push-Ausspielung fehl, darf der auslösende Geldvorgang NICHT scheitern
(analog zum KI-Protokoll-Schutz, Task #793). Deshalb fängt emit_event()
jede Ausnahme der Ausspielung ab und loggt sie nur.
"""
import logging
import random
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

logger = logging.getLogger(__name__)

# Ereignis-Typen (identisch zu RumorNews.EVENT_*).
EVENT_LISTING_CREATED = 'LISTING_CREATED'
EVENT_BID_PLACED = 'BID_PLACED'
EVENT_DEAL_SENT = 'DEAL_SENT'
EVENT_TRANSFER_DONE = 'TRANSFER_DONE'
EVENT_LOAN_DONE = 'LOAN_DONE'


# ── Gerüchte-Texte: je Event-Typ ≥ 8 deutsche Varianten ────────────────────
# Platzhalter: {spieler} {verein_a} {verein_b} {summe} {position} {alter}
_TEMPLATES = {
    EVENT_LISTING_CREATED: [
        '{verein_a} stellt {spieler} auf die Transferliste — Mindestgebot {summe}.',
        'Wechselgerücht: {spieler} ({position}, {alter}) soll {verein_a} für {summe} verlassen.',
        '{spieler} steht bei {verein_a} auf dem Markt — Klubs können ab {summe} zuschlagen.',
        'Insider: {verein_a} öffnet die Tür für {spieler}-Abgang, Preisschild {summe}.',
        'Neu gelistet: {spieler} sucht neue Herausforderung, {verein_a} ruft {summe} auf.',
        '{position} {spieler} zum Verkauf freigegeben — {verein_a} taxiert ihn auf {summe}.',
        'Transferbörse: {spieler} verlässt {verein_a} wohl im Sommer, Basis {summe}.',
        'Poker um {spieler}: {verein_a} listet den {alter}-Jährigen für {summe}.',
        'Abschied bei {verein_a}? {spieler} offen gelistet, Einstieg ab {summe}.',
    ],
    EVENT_BID_PLACED: [
        '{verein_b} legt für {spieler} ein Gebot über {summe} vor.',
        'Bieterschlacht um {spieler}: {verein_b} bietet {summe}.',
        '{verein_b} macht bei {spieler} ernst — {summe} auf dem Tisch.',
        'Angriff auf {spieler}: {verein_b} erhöht auf {summe}.',
        'Gerücht: {verein_b} will {spieler} ({position}) und bietet {summe}.',
        '{summe}! So viel legt {verein_b} laut Insidern für {spieler} hin.',
        'Vorstoß von {verein_b}: {spieler} soll für {summe} kommen.',
        '{verein_b} greift nach {spieler} — Gebot in Höhe von {summe}.',
        'Heiß begehrt: {spieler} lockt {verein_b} mit einem {summe}-Gebot.',
    ],
    EVENT_DEAL_SENT: [
        '{verein_b} soll bei {verein_a} wegen {spieler} angeklopft haben — Volumen {summe}.',
        'Stille Anfrage: {verein_b} interessiert an {spieler}, im Raum stehen {summe}.',
        'Insider: {verein_b} sondiert einen Deal um {spieler} ({summe}).',
        '{spieler} auf dem Zettel von {verein_b} — Anfrage über {summe} bei {verein_a}.',
        'Hinter den Kulissen: {verein_b} und {verein_a} sprechen über {spieler} ({summe}).',
        'Gerücht: {verein_b} will {spieler} verpflichten, Paket rund {summe}.',
        '{verein_b} testet die Schmerzgrenze von {verein_a} bei {spieler} — {summe}.',
        'Transfer-Fühler: {verein_b} fragt {spieler} an, Rede ist von {summe}.',
        'Diskret angefragt: {verein_b} hätte {spieler} gern, Wert {summe}.',
    ],
    EVENT_TRANSFER_DONE: [
        'Fix: {spieler} wechselt von {verein_a} zu {verein_b} für {summe}.',
        'Deal perfekt — {spieler} schließt sich {verein_b} an ({summe}).',
        '{verein_b} verpflichtet {spieler} von {verein_a}, Ablöse {summe}.',
        'Offiziell: {spieler} ({position}, {alter}) ist ein Neuzugang von {verein_b} — {summe}.',
        'Transfer abgeschlossen: {spieler} für {summe} zu {verein_b}.',
        'Es ist vollbracht — {spieler} verlässt {verein_a} Richtung {verein_b} ({summe}).',
        '{verein_b} schnappt sich {spieler}: {summe} fließen an {verein_a}.',
        'Neuzugang bestätigt: {spieler} unterschreibt bei {verein_b}, {summe} Ablöse.',
        'Wechsel durch: {spieler} tauscht {verein_a} gegen {verein_b} für {summe}.',
    ],
    EVENT_LOAN_DONE: [
        'Leih-Deal fix: {spieler} spielt künftig für {verein_b} — Gebühr {summe}.',
        '{verein_b} leiht {spieler} von {verein_a} aus ({summe}).',
        'Auf Leihbasis: {spieler} wechselt zu {verein_b}, {summe} Gebühr.',
        'Offiziell verliehen: {spieler} ({position}) geht zu {verein_b} für {summe}.',
        '{verein_a} gibt {spieler} leihweise an {verein_b} ab — {summe}.',
        'Leihe perfekt — {spieler} sammelt bei {verein_b} Spielpraxis ({summe}).',
        '{verein_b} sichert sich {spieler} als Leihgabe, Gebühr {summe}.',
        'Zwischenstation {verein_b}: {spieler} kommt per Leihe für {summe}.',
        'Leihgeschäft bestätigt: {spieler} von {verein_a} zu {verein_b} ({summe}).',
    ],
}

# Leih-RÜCKKEHR (gleicher Event-Typ LOAN_DONE, eigener Textpool):
# {verein_a} = abgebender Leihverein, {verein_b} = aufnehmender Stammverein.
_TEMPLATES_LOAN_RETURN = [
    'Leihe beendet: {spieler} kehrt von {verein_a} zu {verein_b} zurück.',
    '{spieler} ist zurück — die Leihe bei {verein_a} ist vorbei.',
    'Rückkehrer: {verein_b} begrüßt {spieler} nach Leih-Ende wieder.',
    'Leih-Ende fix: {spieler} verlässt {verein_a} Richtung Stammverein {verein_b}.',
    '{verein_b} holt Leihspieler {spieler} von {verein_a} zurück.',
    'Wieder daheim: {spieler} beendet sein Gastspiel bei {verein_a}.',
    '{spieler} ({position}) kehrt zu {verein_b} zurück — Leihe ausgelaufen.',
    'Abschied von {verein_a}: {spieler} tritt die Rückreise zu {verein_b} an.',
    'Leihstation beendet — {spieler} steht wieder im Kader von {verein_b}.',
]

_TAG = 'Transfergerücht'


# ── Hilfsfunktionen ────────────────────────────────────────────────────────

def _euro(value):
    try:
        v = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return '0 €'
    return f'{v:,}'.replace(',', '.') + ' €'


def _round_million(value):
    """Rundet auf glatte Millionen (mind. 1) für Spannen-Anzeige."""
    v = Decimal(str(value or 0))
    mio = (v / Decimal('1000000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    if mio < 1:
        mio = Decimal('1')
    return int(mio)


def _sum_label(betrag, *, exact, rng):
    """Exakte Summe ODER Spanne innerhalb ±20 %, auf glatte Mio gerundet."""
    if betrag is None or betrag <= 0:
        return 'ungenannter Summe'
    if exact:
        return _euro(betrag)
    b = Decimal(str(betrag))
    lo = _round_million(b * Decimal('0.8'))
    hi = _round_million(b * Decimal('1.2'))
    if hi <= lo:
        hi = lo + 1
    return f'{lo}–{hi} Mio €'


def _param(key, default, saison=None):
    from game.economy.params import get_param
    try:
        return get_param(key, saison)
    except Exception:
        return default


def _p_news(event_type, saison=None):
    table = _param('RUMOR_P_NEWS', {}, saison) or {}
    return float(table.get(event_type, 0.0))


def _p_exact(saison=None):
    return float(_param('RUMOR_P_EXACT', 0.5, saison))


def _pick_outlet(rng):
    """Zufälliges Medium (gleichverteilt), Vereinsredaktion ausgenommen."""
    from game.models import MediaOutlet
    outlets = list(MediaOutlet.objects.exclude(slug='vereinsredaktion'))
    if not outlets:
        outlets = list(MediaOutlet.objects.all())
    return rng.choice(outlets) if outlets else None


def _pos(player):
    hp = getattr(player, 'main_position_1', '') or ''
    if not hp:
        pos = getattr(player, 'main_positions', None) or []
        hp = pos[0] if pos else ''
    return hp or 'Spieler'


def _already_today(player_id, event_type, when):
    """Max. 1 Gerücht pro Vorgang (Spieler+Event-Typ) und Tag.

    Nur Vorabprüfung (spart die Rolls); die harte Garantie liefert der
    UniqueConstraint auf (player, event_type, published_day) — parallele
    Aufrufe enden im IntegrityError-Pfad von _emit_rumor.
    """
    from .models import RumorNews
    if player_id is None:
        return False
    return RumorNews.objects.filter(
        player_id=player_id, event_type=event_type,
        published_day=_day(when),
    ).exists()


def _day(when):
    return (timezone.localdate() if when is None
            else timezone.localtime(when).date())


# ── Öffentlicher Auslöser ──────────────────────────────────────────────────

def emit_event(event_type, *, player=None, club_a=None, club_b=None,
               affected_club=None, betrag=None, saison=None, when=None,
               rng=None, loan_return=False):
    """Verarbeitet ein Transfer-Ereignis (Gerücht würfeln, ausspielen).

    Konvention: club_a = abgebender Verein, club_b = aufnehmender Verein
    (aus Sicht des betroffenen Spielers, NICHT des Vorgangs-Initiators).
    loan_return=True nutzt den Rückkehr-Textpool (Event-Typ bleibt LOAN_DONE).

    Nebenwirkungs-isoliert: jede Ausnahme wird geloggt, nie propagiert —
    der auslösende Geldvorgang darf nie an der Ausspielung scheitern.

    Rückgabe: das erzeugte RumorNews (oder None, wenn kein Gerücht fiel).
    """
    try:
        return _emit_rumor(
            event_type, player=player, club_a=club_a, club_b=club_b,
            affected_club=affected_club, betrag=betrag, saison=saison,
            when=when, rng=rng, loan_return=loan_return)
    except Exception:
        logger.exception('Gerücht-Ausspielung für %s fehlgeschlagen', event_type)
        return None


def _emit_rumor(event_type, *, player, club_a, club_b, affected_club,
                betrag, saison, when, rng, loan_return=False):
    from .models import RumorNews

    if event_type not in _TEMPLATES:
        return None
    rng = rng or random.Random()

    # Roll 1 — erscheint eine News?
    if rng.random() >= _p_news(event_type, saison):
        return None
    # Max. 1 Gerücht pro Vorgang und Tag.
    if player is not None and _already_today(player.pk, event_type, when):
        return None

    outlet = _pick_outlet(rng)
    if outlet is None:
        return None

    # Roll 2 — Summe exakt oder Spanne.
    exact = rng.random() < _p_exact(saison)
    summe_label = _sum_label(betrag, exact=exact, rng=rng)

    ctx = {
        'spieler': player.full_name if player else 'Ein Spieler',
        'verein_a': club_a.name if club_a else 'ein Klub',
        'verein_b': club_b.name if club_b else 'ein Klub',
        'summe': summe_label,
        'position': _pos(player) if player else 'Spieler',
        'alter': (f'{player.age} J.' if player and player.age else '—'),
    }
    pool = (_TEMPLATES_LOAN_RETURN
            if loan_return and event_type == EVENT_LOAN_DONE
            else _TEMPLATES[event_type])
    headline = rng.choice(pool).format(**ctx)[:280]

    # Tages-Dedup DB-erzwungen: UniqueConstraint auf (player, event_type,
    # published_day). Paralleler Doppel-INSERT verliert deterministisch —
    # eigener Savepoint, damit eine umgebende Transaktion intakt bleibt.
    from django.db import IntegrityError, transaction as _tx
    try:
        with _tx.atomic():
            rumor = RumorNews.objects.create(
                event_type=event_type,
                player=player,
                affected_club=affected_club,
                outlet=outlet.name[:80],
                headline=headline,
                sum_mode=RumorNews.SUM_EXACT if exact else RumorNews.SUM_RANGE,
                published_at=when or timezone.now(),
                published_day=_day(when) if player is not None else None,
            )
    except IntegrityError:
        return None  # paralleler Aufruf hat das Tages-Gerücht schon angelegt.
    _emit_rumor_news_item(rumor, outlet, event_type)
    return rumor


def _emit_rumor_news_item(rumor, outlet, event_type):
    """Spiegelt das Gerücht als Vereinsnews-Karte (Master-Spec §5.7 Punkt 5).

    Das Gerücht erscheint in den Vereinsnews des betroffenen Vereins
    (dessen Manager reagieren darf); ohne betroffenen Verein wird keine
    Vereinsnews erzeugt (reines Markt-Gerücht auf der Transfermarkt-Seite).
    """
    from game.models import ClubNewsItem
    if rumor.affected_club_id is None:
        return None
    img = ''
    if rumor.player_id:
        try:
            img = rumor.player.portrait_static_path or ''
        except Exception:
            img = ''
    return ClubNewsItem.objects.create(
        club_id=rumor.affected_club_id,
        title=rumor.headline[:160],
        subtitle=_TAG,
        category='Transfergerücht',
        outlet=outlet.name[:50],
        published_at=timezone.localdate(),
        img_path=img,
    )
