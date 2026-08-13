"""Management-Command: offene Legacy-Transfervorgänge sauber schließen.

Idempotent: Mehrfachausführung schadet nicht — bereits terminale Vorgänge
werden übersprungen.

Schließt:
  1. Offene TransferNegotiation (Status 'gegenforderung') via
     game.economy.negotiation.cancel().  Gibt Reservierungen frei und
     setzt Cooldown (kein Geldfluss).
  2. Offene AITransferOffer (Status 'berechnet' oder 'versendet') via
     storniere_offene_fuer_spieler() — logisch: Alle Angebote an den
     jeweiligen Spieler werden storniert, ohne dass Geld oder Reservierungen
     bewegt werden.

Aufruf:
    python manage.py close_legacy_transfer_flows [--dry-run]
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Schließt offene Legacy-Transfervorgänge (TransferNegotiation + '
        'AITransferOffer) sauber ab.  Idempotent.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Nur zählen, nichts persistieren.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        if dry:
            self.stdout.write(self.style.WARNING(
                '=== DRY-RUN — keine Änderungen werden gespeichert ==='
            ))

        nego_count = self._close_negotiations(dry)
        ai_count = self._close_ai_offers(dry)

        self.stdout.write(self.style.SUCCESS(
            f'\nZusammenfassung:\n'
            f'  TransferNegotiation storniert : {nego_count}\n'
            f'  AITransferOffer storniert      : {ai_count}\n'
            f'{"(DRY-RUN — nichts persistiert)" if dry else ""}'
        ))

    # ------------------------------------------------------------------
    def _close_negotiations(self, dry: bool) -> int:
        """Offene TransferNegotiation (Status 'gegenforderung') stornieren."""
        from game.models import TransferNegotiation
        from game.economy.negotiation import cancel, NegotiationError

        offene = list(
            TransferNegotiation.objects.filter(
                status=TransferNegotiation.STATUS_GEGENFORDERUNG,
            ).select_related('player', 'bidder_club', 'seller_club')
        )

        if not offene:
            self.stdout.write('TransferNegotiation: keine offenen Vorgänge.')
            return 0

        self.stdout.write(
            f'TransferNegotiation: {len(offene)} offene Vorgänge gefunden.'
        )

        count = 0
        for nego in offene:
            label = (
                f'  #{nego.pk} | {nego.player} → {nego.seller_club} '
                f'(Bieter: {nego.bidder_club}, Runde {nego.runde})'
            )
            if dry:
                self.stdout.write(f'[DRY] würde stornieren: {label}')
                count += 1
                continue
            try:
                cancel(nego)
                self.stdout.write(f'  Storniert: {label}')
                count += 1
            except NegotiationError as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f'  Übersprungen (bereits terminal?): {label} — {exc}'
                    )
                )
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(
                    f'  FEHLER bei #{nego.pk}: {exc}'
                )

        return count

    # ------------------------------------------------------------------
    def _close_ai_offers(self, dry: bool) -> int:
        """Offene AITransferOffer (berechnet/versendet) stornieren."""
        from game.models import AITransferOffer
        from game.economy.ai_buyer.offers import storniere_offene_fuer_spieler

        offene = list(
            AITransferOffer.objects.filter(
                status__in=AITransferOffer.OFFENE_STATUS,
            ).select_related('player', 'buyer_club', 'seller_club')
        )

        if not offene:
            self.stdout.write('AITransferOffer: keine offenen Vorgänge.')
            return 0

        self.stdout.write(
            f'AITransferOffer: {len(offene)} offene Vorgänge gefunden.'
        )

        # Storniere je Spieler gebündelt (storniere_offene_fuer_spieler ist
        # idempotent und bereinigt alle offenen Angebote auf diesen Spieler).
        gesehen = set()
        total = 0
        for offer in offene:
            pid = offer.player_id
            if pid in gesehen:
                continue
            gesehen.add(pid)
            label = (
                f'  Spieler #{pid} ({offer.player}) — '
                f'Verein: {offer.seller_club}'
            )
            if dry:
                # Im Dry-Run zählen wir die betroffenen Angebote direkt.
                n_preview = sum(
                    1 for o in offene if o.player_id == pid
                )
                self.stdout.write(
                    f'[DRY] würde stornieren ({n_preview} Angebote): {label}'
                )
                total += n_preview
                continue
            try:
                n = storniere_offene_fuer_spieler(
                    offer.player,
                    grund='Legacy-Transfer-UI abgelöst (close_legacy_transfer_flows).',
                )
                self.stdout.write(f'  Storniert ({n} Angebote): {label}')
                total += n
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(
                    f'  FEHLER bei Spieler #{pid}: {exc}'
                )

        return total
