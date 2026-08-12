"""Push-Katalog des Transfersystems v2 (Master-Spec §7 = Design-Spec §8).

Zentrale, benannte Auslöser für jede in der Spec verbindlich gelistete
Benachrichtigung. Das bestehende Benachrichtigungs-System (game.notifications)
kennt keinen Typ-Enum — die Katalog-Unterscheidung liegt daher präzise in
Titel/Text, NICHT in einem neuen Feld.

Alle Auslöser sind nebenwirkungs-isoliert: schlägt der Versand fehl, darf
der auslösende Geldvorgang NIE scheitern. Deshalb kapselt _safe() jeden
Aufruf und loggt Ausnahmen nur.
"""
import logging

logger = logging.getLogger(__name__)

_MARKT_URL = '/transfers/markt/'
_DEALS_URL = '/transfers/deals/'
_LEIH_URL = '/transfers/leihmarkt/'
_WATCH_URL = '/transfers/beobachtungsliste/'


def _euro(value):
    try:
        v = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return '0 €'
    return f'{v:,}'.replace(',', '.') + ' €'


def _safe(fn):
    try:
        fn()
    except Exception:
        logger.exception('Transfer-Push fehlgeschlagen')


def _catalog(fn):
    """Dekorator: zentraler Nach-Commit-Dispatch für JEDEN Auslöser.

    Registriert den GESAMTEN Auslöser (inkl. Empfänger-Lookups wie
    _watchers/_pin_clubs) via transaction.on_commit: Er läuft erst nach dem
    dauerhaften Commit der äußersten Transaktion (ohne aktive Transaktion
    sofort), nie bei Rollback — und ist vollständig fehler-isoliert: eine
    fehlgeschlagene Query oder ein Versandfehler kann weder den
    Geschäftsvorgang zurückrollen noch nach dessen Commit hochschlagen.
    """
    import functools
    from django.db import transaction

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        def _run():
            try:
                fn(*args, **kwargs)
            except Exception:
                logger.exception('Transfer-Push-Auslöser %s fehlgeschlagen',
                                 fn.__name__)
        transaction.on_commit(_run)
    return wrapper


def _notify_club(club, title, body='', url=''):
    from game.notifications import notify_club
    _safe(lambda: notify_club(club, title, body, url))


def _notify_manager(manager, title, body='', url=''):
    from game.notifications import notify
    _safe(lambda: notify(manager, title, body, url))


def _watchers(player, exclude_club=None):
    """Manager, die den Spieler beobachten (ohne den auslösenden Verein)."""
    from game.models import WatchlistEntry
    qs = (WatchlistEntry.objects.filter(player=player)
          .select_related('manager', 'manager__managed_club'))
    out = []
    for e in qs:
        m = e.manager
        club = getattr(m, 'managed_club', None)
        if exclude_club is not None and club is not None \
                and club.pk == exclude_club.pk:
            continue
        out.append(m)
    return out


# ── 1. Beobachteter Spieler ────────────────────────────────────────────────

@_catalog
def watchlist_listed(player, min_bid):
    for m in _watchers(player):
        _notify_manager(
            m, f'Beobachtet: {player.full_name} auf der Transferliste',
            f'Mindestgebot {_euro(min_bid)}.', _MARKT_URL)


@_catalog
def watchlist_loan_listed(player):
    for m in _watchers(player):
        _notify_manager(
            m, f'Beobachtet: {player.full_name} auf dem Leihmarkt',
            'Ein beobachteter Spieler steht zur Leihe bereit.', _LEIH_URL)


@_catalog
def watchlist_status_changed(player, status_label):
    for m in _watchers(player):
        _notify_manager(
            m, f'Beobachtet: {player.full_name} — Status geändert',
            f'Neuer Kader-Status: {status_label}.', _WATCH_URL)


# ── 2. Gepinntes Listing ───────────────────────────────────────────────────

def _pin_clubs(listing, exclude_club=None):
    from .models import ListingPin
    from game.models import Club
    ids = set(ListingPin.objects.filter(listing=listing)
              .values_list('club_id', flat=True))
    if exclude_club is not None:
        ids.discard(exclude_club.pk)
    return list(Club.objects.filter(pk__in=ids))


@_catalog
def pinned_new_bid(listing, club, amount):
    for c in _pin_clubs(listing, exclude_club=club):
        _notify_club(
            c, f'Gepinnt: neues Gebot für {listing.player.full_name}',
            f'{club.name} bietet {_euro(amount)}.', _MARKT_URL)


@_catalog
def pinned_extended(listing):
    for c in _pin_clubs(listing):
        _notify_club(
            c, f'Gepinnt: Auktion verlängert — {listing.player.full_name}',
            'Anti-Sniping: die Auktion wurde um 24 Stunden verlängert.',
            _MARKT_URL)


@_catalog
def pinned_bought_now(listing, buyer):
    for c in _pin_clubs(listing, exclude_club=buyer):
        _notify_club(
            c, f'Gepinnt: Sofortkauf — {listing.player.full_name}',
            f'{buyer.name} hat den Spieler sofort gekauft.', _MARKT_URL)


@_catalog
def pinned_ended(listing):
    for c in _pin_clubs(listing):
        _notify_club(
            c, f'Gepinnt: Auktion beendet — {listing.player.full_name}',
            'Die beobachtete Auktion ist beendet.', _MARKT_URL)


# ── 3. Eigenes Gebot ───────────────────────────────────────────────────────

@_catalog
def bid_outbid(prev_club, listing, new_amount):
    _notify_club(
        prev_club, f'Überboten: {listing.player.full_name}',
        f'Dein Gebot wurde überboten — jetzt {_euro(new_amount)}. '
        'Reservierung freigegeben.', _MARKT_URL)


@_catalog
def auction_won(club, listing, amount):
    _notify_club(
        club, f'Zuschlag erhalten: {listing.player.full_name}',
        f'Du hast die Auktion für {_euro(amount)} gewonnen.', _MARKT_URL)


@_catalog
def auction_lost(club, listing):
    _notify_club(
        club, f'Auktion beendet: {listing.player.full_name}',
        'Deine Auktion wurde ohne Zuschlag für dich beendet — '
        'Reservierung freigegeben.', _MARKT_URL)


# ── 4. Deal-/Leihanfrage ───────────────────────────────────────────────────

@_catalog
def deal_received(deal):
    is_loan = getattr(deal, 'typ', None) == 'LOAN'
    art = 'Leihanfrage' if is_loan else 'Deal-Anfrage'
    _notify_club(
        deal.to_club, f'{art} von {deal.from_club.name}',
        'Neue Anfrage unter „Meine Deals".', _DEALS_URL)


@_catalog
def deal_accepted(deal):
    _notify_club(
        deal.from_club, f'Anfrage angenommen — {deal.to_club.name}',
        'Deine Anfrage wurde angenommen und sofort vollzogen.', _DEALS_URL)


@_catalog
def deal_declined(deal):
    _notify_club(
        deal.from_club, f'Anfrage abgelehnt — {deal.to_club.name}',
        'Deine Anfrage wurde abgelehnt. Reservierung freigegeben.', _DEALS_URL)


@_catalog
def deal_withdrawn(deal):
    _notify_club(
        deal.to_club, f'Anfrage zurückgezogen — {deal.from_club.name}',
        'Der Initiator hat die Anfrage zurückgezogen.', _DEALS_URL)


@_catalog
def deal_expired(deal):
    _notify_club(
        deal.from_club, 'Anfrage abgelaufen',
        f'Deine Anfrage an {deal.to_club.name} ist abgelaufen. '
        'Reservierung freigegeben.', _DEALS_URL)
    _notify_club(
        deal.to_club, 'Anfrage abgelaufen',
        f'Die Anfrage von {deal.from_club.name} ist abgelaufen.', _DEALS_URL)


# ── 5. Rückruf ─────────────────────────────────────────────────────────────

@_catalog
def recall_requested(loan):
    _notify_club(
        loan.loan_club, f'Rückruf-Anfrage: {loan.player.full_name}',
        f'{loan.owner_club.name} möchte den Spieler zurück — '
        'deine Zustimmung ist erforderlich.', _DEALS_URL)


@_catalog
def recall_answered(loan, accepted):
    if accepted:
        _notify_club(
            loan.owner_club, f'Rückruf angenommen: {loan.player.full_name}',
            f'{loan.loan_club.name} hat zugestimmt — der Spieler kehrt zurück.',
            _DEALS_URL)
    else:
        _notify_club(
            loan.owner_club, f'Rückruf abgelehnt: {loan.player.full_name}',
            f'{loan.loan_club.name} hat den Rückruf abgelehnt.', _DEALS_URL)


# ── 6. Meldung an die Transferaufsicht ─────────────────────────────────────

def _oversight_managers():
    """Empfänger der Transferaufsicht: handlungsfähige Staff-Manager.

    Die Aufsicht ist im Produkt der Creator-Mode/Admin — geroutet wird NUR
    an Staff-Manager, die die Meldung im Django-Admin (TransferReport)
    auch tatsächlich bearbeiten dürfen (change-Permission bzw. Superuser).
    Sonst erhielte jemand einen Link, den er nicht öffnen kann.
    """
    from game.models import ManagerProfile
    qs = (ManagerProfile.objects.filter(user__is_staff=True)
          .select_related('user'))
    return [m for m in qs
            if m.user.has_perm('game.change_transferreport')]


@_catalog
def report_received(report):
    # Eingangsbestätigung an den Melder …
    _notify_club(
        report.reporter_club, 'Meldung eingegangen',
        'Deine Transfer-Meldung wurde an die Transferaufsicht übermittelt.',
        _DEALS_URL)
    # … und Routing an die Aufsicht (Staff-Manager) mit Bearbeitungs-Link.
    admin_url = f'/admin/game/transferreport/{report.pk}/change/'
    grund = (report.reason or '')[:120]
    for m in _oversight_managers():
        _notify_manager(
            m, 'Neue Transfer-Meldung (Aufsicht)',
            f'{report.reporter_club.name}: {grund}', admin_url)


@_catalog
def report_resolved(report, result_label):
    _notify_club(
        report.reporter_club, 'Meldung bearbeitet',
        f'Ergebnis deiner Meldung: {result_label}.', _DEALS_URL)


# ── Zusätzlich aus §4.4: Kadergrenzen & Admin ──────────────────────────────

@_catalog
def squad_limit_note(club, text):
    _notify_club(club, 'Kadergrenzen-Hinweis', text, _DEALS_URL)


@_catalog
def pending_cancelled_limit(club, text):
    """Storno eines WP/SE-Pendings am Stichtag (Kadergrenze/Zustand)."""
    _notify_club(club, 'Transfer storniert (Kadergrenze)', text, _DEALS_URL)


@_catalog
def admin_cancelled(record, club, grund=''):
    body = 'Ein Transfer wurde von der Aufsicht storniert.'
    if grund:
        body += f' Grund: {grund}'
    _notify_club(club, 'Transfer storniert (Admin)', body, _DEALS_URL)


@_catalog
def admin_transfer(club, text):
    _notify_club(club, 'Admin-Transfer', text, _DEALS_URL)
