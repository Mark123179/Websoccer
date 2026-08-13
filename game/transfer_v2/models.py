"""Transfersystem v2 — Datenmodell (Design-Spec §13.3 + Master-Spec §4.1).

Additiv zum Bestand. Kein Feld/Modell ohne Deckung in Prototyp/Spec.
Geldbeträge als DecimalField(max_digits=15, decimal_places=2) wie im
Finanzsystem. Zeiten in UTC (Anzeige Europe/Berlin erfolgt im Frontend).
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

# Konsistent mit Finanzsystem: 15/2 für Geld.
_MONEY = dict(max_digits=15, decimal_places=2)


class TransferListing(models.Model):
    """Auktions-Listing eines Spielers (Master-Spec §4.1/§4.2).

    seller=NULL → Vereinsloser (FREE_AGENT): min_bid = aktueller MW,
    ends_at bleibt NULL bis zum 1. Gebot (dann now + 24 h). Normale
    Listings: ends_at = listed_at + duration_days.
    """

    TIMING_SOFORT = 'SOFORT'
    TIMING_WP = 'WP'
    TIMING_SE = 'SE'
    TIMING_CHOICES = [
        (TIMING_SOFORT, 'Sofort'),
        (TIMING_WP, 'Winterpause'),
        (TIMING_SE, 'Saisonende'),
    ]

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_SOLD = 'SOLD'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Aktiv'),
        (STATUS_SOLD, 'Verkauft'),
        (STATUS_CANCELLED, 'Storniert'),
        (STATUS_EXPIRED, 'Abgelaufen'),
    ]

    DURATION_CHOICES = [(d, f'{d} Tage') for d in (1, 2, 3, 5, 7)]

    player = models.ForeignKey(
        'game.Player', on_delete=models.CASCADE,
        related_name='transfer_listings', verbose_name='Spieler',
    )
    seller = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE,
        related_name='transfer_listings', null=True, blank=True,
        verbose_name='Verkäufer (NULL = vereinslos)',
    )
    min_bid = models.DecimalField(
        **_MONEY, verbose_name='Mindestgebot (€)',
        validators=[MinValueValidator(Decimal('0'))],
    )
    buy_now = models.DecimalField(
        **_MONEY, null=True, blank=True, verbose_name='Sofortkauf (€)',
    )
    timing = models.CharField(
        max_length=6, choices=TIMING_CHOICES, default=TIMING_SOFORT,
        verbose_name='Transferzeitpunkt',
    )
    duration_days = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Laufzeit (Tage)',
        help_text='NULL bei Vereinslosen (24 h ab 1. Gebot).',
    )
    listed_at = models.DateTimeField(default=timezone.now, verbose_name='Gelistet am')
    ends_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Endet am',
        help_text='NULL bis zum 1. Gebot bei Vereinslosen.',
    )
    extensions = models.PositiveSmallIntegerField(
        default=0, verbose_name='Anti-Sniping-Verlängerungen',
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'game'
        ordering = ['ends_at', 'id']
        indexes = [
            models.Index(fields=['status', 'ends_at']),
            models.Index(fields=['seller', 'status']),
        ]
        verbose_name = 'Transfer-Listing'
        verbose_name_plural = 'Transfer-Listings'

    @property
    def is_free_agent(self):
        return self.seller_id is None

    def __str__(self):
        return f'Listing #{self.pk} {self.player} [{self.status}]'


class TransferBid(models.Model):
    """Bindendes Gebot (kein Auto-Bieten, kein max_amount)."""

    listing = models.ForeignKey(
        TransferListing, on_delete=models.CASCADE,
        related_name='bids', verbose_name='Listing',
    )
    club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE,
        related_name='transfer_bids_v2', verbose_name='Bietender Verein',
    )
    amount = models.DecimalField(**_MONEY, verbose_name='Betrag (€)')
    is_leading = models.BooleanField(
        default=False, verbose_name='Aktuell führend',
        help_text='Genau ein führendes Gebot je aktivem Listing.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'game'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['listing', '-created_at']),
            models.Index(fields=['club', 'is_leading']),
        ]
        verbose_name = 'Gebot'
        verbose_name_plural = 'Gebote'

    def __str__(self):
        return f'{self.club} bietet {self.amount:,.0f} € auf {self.listing_id}'


class ListingPin(models.Model):
    """Pin = Push-Abo für alle Ereignisse eines Listings; öffentliche Anzahl."""

    listing = models.ForeignKey(
        TransferListing, on_delete=models.CASCADE,
        related_name='pins', verbose_name='Listing',
    )
    club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE,
        related_name='listing_pins', verbose_name='Verein',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'game'
        constraints = [
            models.UniqueConstraint(
                fields=['listing', 'club'], name='unique_listing_pin',
            ),
        ]
        verbose_name = 'Listing-Pin'
        verbose_name_plural = 'Listing-Pins'


class SquadOffer(models.Model):
    """"Kader anbieten"-Status je Spieler (Default UVK)."""

    STATUS_ALL = 'ALL'
    STATUS_SWAP = 'SWAP'
    STATUS_CASH = 'CASH'
    STATUS_SWAP_CASH = 'SWAP_CASH'
    STATUS_LOAN = 'LOAN'
    STATUS_UVK = 'UVK'
    STATUS_CHOICES = [
        (STATUS_ALL, 'Alle Angebote'),
        (STATUS_SWAP, 'Tausch'),
        (STATUS_CASH, 'Geld'),
        (STATUS_SWAP_CASH, 'Tausch/Geld'),
        (STATUS_LOAN, 'Leihe'),
        (STATUS_UVK, 'Unverkäuflich'),
    ]

    player = models.OneToOneField(
        'game.Player', on_delete=models.CASCADE,
        related_name='squad_offer', verbose_name='Spieler',
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_UVK,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'game'
        verbose_name = 'Kader-Angebot'
        verbose_name_plural = 'Kader-Angebote'


class DealRequest(models.Model):
    """Deal-/Leihanfrage (Master-Spec §4.3), 7 Tage Laufzeit."""

    TYP_SWAP = 'SWAP'
    TYP_CASH = 'CASH'
    TYP_SWAP_CASH = 'SWAP_CASH'
    TYP_LOAN = 'LOAN'
    TYP_CHOICES = [
        (TYP_SWAP, 'Tausch'),
        (TYP_CASH, 'Geld'),
        (TYP_SWAP_CASH, 'Tausch/Geld'),
        (TYP_LOAN, 'Leihanfrage'),
    ]

    STATUS_OPEN = 'OPEN'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_DECLINED = 'DECLINED'
    STATUS_WITHDRAWN = 'WITHDRAWN'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Offen'),
        (STATUS_ACCEPTED, 'Angenommen'),
        (STATUS_DECLINED, 'Abgelehnt'),
        (STATUS_WITHDRAWN, 'Zurückgezogen'),
        (STATUS_EXPIRED, 'Abgelaufen'),
    ]

    from_club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE,
        related_name='deal_requests_sent', verbose_name='Initiator',
    )
    to_club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE,
        related_name='deal_requests_received', verbose_name='Empfänger',
    )
    typ = models.CharField(max_length=10, choices=TYP_CHOICES)
    timing = models.CharField(
        max_length=6, choices=TransferListing.TIMING_CHOICES,
        default=TransferListing.TIMING_SOFORT,
    )
    cash_from = models.DecimalField(
        **_MONEY, default=Decimal('0'), verbose_name='Geld vom Initiator',
    )
    cash_to = models.DecimalField(
        **_MONEY, default=Decimal('0'), verbose_name='Geld vom Empfänger',
    )
    # Leih-Konditionen (nur typ=LOAN gesetzt).
    loan_until = models.CharField(
        max_length=6, choices=[(TransferListing.TIMING_WP, 'Winterpause'),
                               (TransferListing.TIMING_SE, 'Saisonende')],
        blank=True, default='',
    )
    loan_fee = models.DecimalField(**_MONEY, null=True, blank=True)
    loan_buy_option = models.DecimalField(**_MONEY, null=True, blank=True)
    message = models.CharField(max_length=280, blank=True, default='')
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name='Läuft ab am')
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'game'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['to_club', 'status']),
            models.Index(fields=['from_club', 'status']),
        ]
        verbose_name = 'Deal-Anfrage'
        verbose_name_plural = 'Deal-Anfragen'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Deal #{self.pk} {self.from_club}→{self.to_club} [{self.status}]'


class DealRequestPlayer(models.Model):
    """Spieler eines Deals — max 5 je Seite (DB-Constraint + UI)."""

    SIDE_FROM = 'FROM'
    SIDE_TO = 'TO'
    SIDE_CHOICES = [(SIDE_FROM, 'Initiator'), (SIDE_TO, 'Empfänger')]

    request = models.ForeignKey(
        DealRequest, on_delete=models.CASCADE, related_name='players',
    )
    player = models.ForeignKey(
        'game.Player', on_delete=models.CASCADE,
        related_name='deal_request_entries',
    )
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)

    class Meta:
        app_label = 'game'
        constraints = [
            models.UniqueConstraint(
                fields=['request', 'player'], name='unique_deal_request_player',
            ),
        ]
        verbose_name = 'Deal-Spieler'
        verbose_name_plural = 'Deal-Spieler'


class LoanListing(models.Model):
    """Leihmarkt-Listing (Master-Spec §4.1 Ergänzung)."""

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_LOANED = 'LOANED'
    STATUS_WITHDRAWN = 'WITHDRAWN'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Aktiv'),
        (STATUS_LOANED, 'Verliehen'),
        (STATUS_WITHDRAWN, 'Zurückgezogen'),
    ]

    UNTIL_WP = 'WP'
    UNTIL_SE = 'SE'
    UNTIL_CHOICES = [(UNTIL_WP, 'Winterpause'), (UNTIL_SE, 'Saisonende')]

    player = models.ForeignKey(
        'game.Player', on_delete=models.CASCADE,
        related_name='loan_listings', verbose_name='Spieler',
    )
    owner_club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE,
        related_name='loan_listings', verbose_name='Stammverein',
    )
    fee_asking = models.DecimalField(
        **_MONEY, verbose_name='Leihgebühr (€)',
        help_text='≥ 1.000.000 € (0 € nur Partnerverein).',
    )
    until = models.CharField(max_length=2, choices=UNTIL_CHOICES)
    buy_option_price = models.DecimalField(**_MONEY, null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'game'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status'])]
        verbose_name = 'Leih-Listing'
        verbose_name_plural = 'Leih-Listings'


class Loan(models.Model):
    """Aktives/beendetes Leihverhältnis."""

    STARTED_VIA_LISTING = 'LISTING'
    STARTED_VIA_DEAL = 'DEAL'
    STARTED_VIA_CHOICES = [
        (STARTED_VIA_LISTING, 'Leihmarkt'),
        (STARTED_VIA_DEAL, 'Deal-Anfrage'),
    ]

    player = models.ForeignKey(
        'game.Player', on_delete=models.CASCADE, related_name='loans_v2',
    )
    owner_club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE, related_name='loans_out',
        verbose_name='Stammverein',
    )
    loan_club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE, related_name='loans_in',
        verbose_name='Leihverein',
    )
    fee = models.DecimalField(**_MONEY, verbose_name='Leihgebühr (€)')
    until = models.CharField(max_length=2, choices=LoanListing.UNTIL_CHOICES)
    buy_option = models.DecimalField(**_MONEY, null=True, blank=True)
    started_via = models.CharField(
        max_length=8, choices=STARTED_VIA_CHOICES,
        default=STARTED_VIA_LISTING,
    )
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    recall_requested = models.BooleanField(default=False)
    recall_requested_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'game'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['owner_club', 'ended_at']),
            models.Index(fields=['loan_club', 'ended_at']),
        ]
        verbose_name = 'Leihe'
        verbose_name_plural = 'Leihen'

    @property
    def is_active(self):
        return self.ended_at is None


class TransferRecord(models.Model):
    """Historie-Eintrag; jeder Vollzug erzeugt genau einen (Master-Spec §4.4)."""

    KIND_CASH = 'CASH'
    KIND_SWAP = 'SWAP'
    KIND_LOAN = 'LOAN'
    KIND_OPTION = 'OPTION'
    KIND_ADMIN = 'ADMIN'
    KIND_FREE = 'FREE'  # Vereinsloser Wechsel.
    KIND_CHOICES = [
        (KIND_CASH, 'Kauf'),
        (KIND_SWAP, 'Tausch'),
        (KIND_LOAN, 'Leihe'),
        (KIND_OPTION, 'Kaufoption gezogen'),
        (KIND_ADMIN, 'Admin-Transfer'),
        (KIND_FREE, 'Ablösefrei'),
    ]

    LOAN_EVENT_START = 'START'
    LOAN_EVENT_RETURN = 'RETURN'
    LOAN_EVENT_CHOICES = [
        (LOAN_EVENT_START, 'Leihstart'),
        (LOAN_EVENT_RETURN, 'Rückkehr'),
    ]

    date = models.DateField(default=timezone.localdate)
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    timing = models.CharField(
        max_length=6, choices=TransferListing.TIMING_CHOICES,
        default=TransferListing.TIMING_SOFORT,
    )
    club_a = models.ForeignKey(
        'game.Club', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfer_records_a', verbose_name='Verein A (abgebend)',
    )
    club_b = models.ForeignKey(
        'game.Club', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfer_records_b', verbose_name='Verein B (aufnehmend)',
    )
    cash_a = models.DecimalField(**_MONEY, default=Decimal('0'))
    cash_b = models.DecimalField(**_MONEY, default=Decimal('0'))
    # Leih-Spezifika.
    loan_event = models.CharField(
        max_length=6, choices=LOAN_EVENT_CHOICES, blank=True, default='',
    )
    loan_until = models.CharField(
        max_length=2, choices=LoanListing.UNTIL_CHOICES, blank=True, default='',
    )
    is_admin = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(
        default=False, verbose_name='Admin-storniert',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'game'
        ordering = ['-date', '-id']
        indexes = [
            models.Index(fields=['kind', '-date']),
            models.Index(fields=['-date']),
        ]
        verbose_name = 'Transfer-Historieneintrag'
        verbose_name_plural = 'Transfer-Historie'

    def __str__(self):
        return f'Record #{self.pk} {self.get_kind_display()} {self.date}'


class TransferRecordPlayer(models.Model):
    """Beteiligter Spieler eines Historieneintrags (mit MW-Snapshot)."""

    SIDE_A = 'A'
    SIDE_B = 'B'
    SIDE_CHOICES = [(SIDE_A, 'Von A'), (SIDE_B, 'Von B')]

    record = models.ForeignKey(
        TransferRecord, on_delete=models.CASCADE, related_name='players',
    )
    player = models.ForeignKey(
        'game.Player', on_delete=models.SET_NULL, null=True,
        related_name='transfer_record_entries',
    )
    side = models.CharField(max_length=1, choices=SIDE_CHOICES)
    market_value_at_transfer = models.DecimalField(**_MONEY, null=True, blank=True)

    class Meta:
        app_label = 'game'
        verbose_name = 'Historie-Spieler'
        verbose_name_plural = 'Historie-Spieler'


class YouthLevyPayment(models.Model):
    """Gebuchte Jugendabgabe je Ausbildungsverein (min. 50.000 €)."""

    record = models.ForeignKey(
        TransferRecord, on_delete=models.CASCADE, related_name='youth_levies',
    )
    player = models.ForeignKey(
        'game.Player', on_delete=models.SET_NULL, null=True,
        related_name='youth_levy_payments',
    )
    payer_club = models.ForeignKey(
        'game.Club', on_delete=models.SET_NULL, null=True,
        related_name='youth_levies_paid',
    )
    receiver_club = models.ForeignKey(
        'game.Club', on_delete=models.SET_NULL, null=True,
        related_name='youth_levies_received',
    )
    percent = models.DecimalField(max_digits=6, decimal_places=3)
    amount = models.DecimalField(**_MONEY)

    class Meta:
        app_label = 'game'
        verbose_name = 'Jugendabgabe-Buchung'
        verbose_name_plural = 'Jugendabgabe-Buchungen'


class TransferReport(models.Model):
    """Melde-Eintrag an die Transferaufsicht (Creator-Mode/Sportgericht)."""

    STATUS_OPEN = 'OPEN'
    STATUS_DISMISSED = 'DISMISSED'
    STATUS_UNDER_REVIEW = 'UNDER_REVIEW'
    STATUS_CONFIRMED = 'CONFIRMED'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Offen'),
        (STATUS_DISMISSED, 'Abgewiesen'),
        (STATUS_UNDER_REVIEW, 'In Überprüfung (Sportgericht)'),
        (STATUS_CONFIRMED, 'Bestätigt (Sportgericht)'),
    ]

    record = models.ForeignKey(
        TransferRecord, on_delete=models.CASCADE, related_name='reports',
    )
    reporter_club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE, related_name='transfer_reports',
    )
    reason = models.CharField(max_length=500, verbose_name='Begründung (Pflicht)')
    status = models.CharField(
        max_length=14, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'game'
        ordering = ['created_at']  # chronologisch, keine Auto-Vorsortierung.
        verbose_name = 'Transfer-Meldung'
        verbose_name_plural = 'Transfer-Meldungen'


class TransferLock(models.Model):
    """Wechselsperre 21 Tage — Persistenz für Anzeige/Prüfung."""

    player = models.ForeignKey(
        'game.Player', on_delete=models.CASCADE, related_name='transfer_locks',
    )
    locked_until = models.DateField(verbose_name='Gesperrt bis')
    source_record = models.ForeignKey(
        TransferRecord, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transfer_locks',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'game'
        ordering = ['-locked_until']
        indexes = [models.Index(fields=['player', 'locked_until'])]
        verbose_name = 'Wechselsperre'
        verbose_name_plural = 'Wechselsperren'


class PendingTransfer(models.Model):
    """Aufgeschobener Spielerwechsel für WP/SE (Geld floss bereits sofort)."""

    SOURCE_LISTING = 'LISTING'
    SOURCE_DEAL = 'DEAL'
    SOURCE_OPTION = 'OPTION'
    SOURCE_CHOICES = [
        (SOURCE_LISTING, 'Listing'),
        (SOURCE_DEAL, 'Deal'),
        (SOURCE_OPTION, 'Kaufoption'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_EXECUTED = 'EXECUTED'
    STATUS_CANCELLED_ADMIN = 'CANCELLED_ADMIN'
    STATUS_CANCELLED_LIMIT = 'CANCELLED_LIMIT'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ausstehend'),
        (STATUS_EXECUTED, 'Vollzogen'),
        (STATUS_CANCELLED_ADMIN, 'Admin-storniert'),
        (STATUS_CANCELLED_LIMIT, 'Kadergrenzen-Storno'),
    ]

    player = models.ForeignKey(
        'game.Player', on_delete=models.CASCADE, related_name='pending_transfers',
    )
    from_club = models.ForeignKey(
        'game.Club', on_delete=models.SET_NULL, null=True,
        related_name='pending_transfers_out',
    )
    to_club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE,
        related_name='pending_transfers_in',
    )
    execute_at = models.DateField(verbose_name='Vollzug am (WP/SE-Datum)')
    source = models.CharField(max_length=8, choices=SOURCE_CHOICES)
    record = models.ForeignKey(
        TransferRecord, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pending_transfers',
        help_text='Historieneintrag, der bereits beim Zuschlag entstand.',
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'game'
        ordering = ['execute_at', 'id']
        indexes = [models.Index(fields=['status', 'execute_at'])]
        verbose_name = 'Ausstehender Transfer'
        verbose_name_plural = 'Ausstehende Transfers'


class ClubPartnership(models.Model):
    """Vereinspartnerschaft — 0-€-Leihgebühr-Ausnahme (Creator-gepflegt)."""

    club_a = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE, related_name='partnerships_a',
    )
    club_b = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE, related_name='partnerships_b',
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'game'
        verbose_name = 'Vereinspartnerschaft'
        verbose_name_plural = 'Vereinspartnerschaften'

    @staticmethod
    def are_partners(club_a, club_b):
        if club_a is None or club_b is None:
            return False
        from django.db.models import Q
        a, b = club_a.pk, club_b.pk
        return ClubPartnership.objects.filter(
            active=True,
        ).filter(
            Q(club_a_id=a, club_b_id=b) | Q(club_a_id=b, club_b_id=a),
        ).exists()


class RumorNews(models.Model):
    """Transfergerücht (Backend-Vorstufe; Ausspielung folgt in Push-Aufgabe)."""

    EVENT_LISTING_CREATED = 'LISTING_CREATED'
    EVENT_BID_PLACED = 'BID_PLACED'
    EVENT_DEAL_SENT = 'DEAL_SENT'
    EVENT_TRANSFER_DONE = 'TRANSFER_DONE'
    EVENT_LOAN_DONE = 'LOAN_DONE'
    EVENT_CHOICES = [
        (EVENT_LISTING_CREATED, 'Listing erstellt'),
        (EVENT_BID_PLACED, 'Gebot abgegeben'),
        (EVENT_DEAL_SENT, 'Anfrage gesendet'),
        (EVENT_TRANSFER_DONE, 'Transfer vollzogen'),
        (EVENT_LOAN_DONE, 'Leihe vollzogen'),
    ]

    SUM_EXACT = 'EXACT'
    SUM_RANGE = 'RANGE'
    SUM_MODE_CHOICES = [(SUM_EXACT, 'Exakt'), (SUM_RANGE, 'Spanne')]

    REACTION_DENIED = 'DENIED'
    REACTION_NO_COMMENT = 'NO_COMMENT'
    REACTION_CONFIRMED = 'CONFIRMED'
    REACTION_CHOICES = [
        (REACTION_DENIED, 'Dementiert'),
        (REACTION_NO_COMMENT, 'Kein Kommentar'),
        (REACTION_CONFIRMED, 'Bestätigt'),
    ]

    event_type = models.CharField(max_length=16, choices=EVENT_CHOICES)
    player = models.ForeignKey(
        'game.Player', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rumor_news',
    )
    affected_club = models.ForeignKey(
        'game.Club', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rumor_news',
        help_text='Verein, dessen Manager reagieren darf (eigener Verein).',
    )
    outlet = models.CharField(max_length=80)
    headline = models.CharField(max_length=280)
    sum_mode = models.CharField(
        max_length=6, choices=SUM_MODE_CHOICES, default=SUM_EXACT,
    )
    reaction = models.CharField(
        max_length=10, choices=REACTION_CHOICES, blank=True, default='',
    )
    reaction_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(default=timezone.now)
    published_day = models.DateField(
        null=True, blank=True,
        help_text='Dedup-Tag: max. 1 Gerücht je Spieler+Event-Typ+Tag. '
                  'Bei Spieler-Gerüchten PFLICHT (CheckConstraint + '
                  'save()-Autofill); NULL nur ohne Spieler.',
    )

    def save(self, *args, **kwargs):
        # Invariante: Spieler-Gerücht ⇒ Dedup-Tag gesetzt. Autofill deckt
        # ORM-/Admin-Erzeugung ab; bulk_create-Umgehungen fängt der
        # CheckConstraint auf DB-Ebene.
        if self.player_id and self.published_day is None:
            base = self.published_at or timezone.now()
            self.published_day = timezone.localtime(base).date()
        super().save(*args, **kwargs)

    class Meta:
        app_label = 'game'
        ordering = ['-published_at']
        indexes = [models.Index(fields=['-published_at'])]
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'event_type', 'published_day'],
                condition=models.Q(player__isnull=False,
                                   published_day__isnull=False),
                name='uniq_rumor_player_event_day',
            ),
            models.CheckConstraint(
                condition=(models.Q(player__isnull=True)
                           | models.Q(published_day__isnull=False)),
                name='rumor_player_requires_day',
            ),
        ]
        verbose_name = 'Transfergerücht'
        verbose_name_plural = 'Transfergerüchte'


class PositionBarometer(models.Model):
    """Angebot/Nachfrage je Position (täglicher Job, KEINE eigene UI)."""

    position = models.CharField(max_length=10, unique=True)
    supply = models.PositiveIntegerField(default=0, verbose_name='Angebot')
    demand = models.PositiveIntegerField(default=0, verbose_name='Nachfrage')
    weight = models.DecimalField(
        max_digits=5, decimal_places=3, default=Decimal('1.000'),
        verbose_name='Preisgewicht',
        help_text='> 1 = Nachfrageüberhang (teurer), < 1 = Angebotsüberhang.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'game'
        verbose_name = 'Positionsbarometer'
        verbose_name_plural = 'Positionsbarometer'


# ── Phase 2 (Regeln fixiert, KEINE Logik/UI in Task #819) ─────────────────

class SellOnClause(models.Model):
    """Weiterverkaufsbeteiligung (Phase 2 — nur Modell-Vorbereitung)."""

    player = models.ForeignKey(
        'game.Player', on_delete=models.CASCADE, related_name='sell_on_clauses',
    )
    beneficiary_club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE, related_name='sell_on_clauses',
    )
    percent = models.PositiveSmallIntegerField(help_text='5–20 %.')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'game'
        verbose_name = 'Weiterverkaufsbeteiligung'
        verbose_name_plural = 'Weiterverkaufsbeteiligungen'


class BuybackClause(models.Model):
    """Rückkaufoption (Phase 2 — nur Modell-Vorbereitung)."""

    player = models.ForeignKey(
        'game.Player', on_delete=models.CASCADE, related_name='buyback_clauses',
    )
    holder_club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE, related_name='buyback_clauses',
    )
    price = models.DecimalField(**_MONEY)
    deadline = models.DateField()
    preemption_until = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'game'
        verbose_name = 'Rückkaufoption'
        verbose_name_plural = 'Rückkaufoptionen'


# ── Task #824: Creator-Transferaufsicht ───────────────────────────────────

class SquadLimitNote(models.Model):
    """Kadergrenzen-Vermerk (automatisch bei WP/SE-Storno + manuell)."""

    STATUS_OPEN = 'OPEN'
    STATUS_SPORTGERICHT = 'SPORTGERICHT'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Offen'),
        (STATUS_SPORTGERICHT, 'Im Sportgericht'),
    ]

    club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE,
        related_name='squad_limit_notes', verbose_name='Verein',
    )
    player = models.ForeignKey(
        'game.Player', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='squad_limit_notes', verbose_name='Spieler',
    )
    text = models.CharField(max_length=500, verbose_name='Text')
    status = models.CharField(
        max_length=14, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'game'
        ordering = ['-created_at']
        verbose_name = 'Kadergrenzen-Vermerk'
        verbose_name_plural = 'Kadergrenzen-Vermerke'

    def __str__(self):
        return f'SquadLimitNote #{self.pk} [{self.club}] {self.status}'


class CreatorActionLog(models.Model):
    """Protokoll von Creator-Aktionen (Transferaufsicht)."""

    actor = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='creator_action_logs', verbose_name='Akteur',
    )
    action = models.CharField(max_length=40, verbose_name='Aktion')
    target = models.CharField(max_length=200, verbose_name='Ziel')
    details = models.JSONField(default=dict, blank=True, verbose_name='Details')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'game'
        ordering = ['-created_at']
        verbose_name = 'Creator-Aktionsprotokoll'
        verbose_name_plural = 'Creator-Aktionsprotokolle'

    def __str__(self):
        return f'CreatorActionLog #{self.pk} {self.action} by {self.actor}'
