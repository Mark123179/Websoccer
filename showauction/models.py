"""Show-Auktion (TV-Transfershow) — Datenmodell (Spec §6).

Typen sind DATEN, kein Code: Ein Preset ist eine Belegung der 16
Regel-Achsen (validator.validate_config). Die Auktion friert diese
Belegung als config_snapshot ein — spätere Preset-Änderungen wirken
nie auf laufende Auktionen zurück (Spec E24).
"""
import os
import uuid

from django.conf import settings
from django.db import models


def hero_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.png'
    return f'showauction/hero/{uuid.uuid4().hex}{ext}'


def logo_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or '.png'
    return f'showauction/logo/{uuid.uuid4().hex}{ext}'


class ShowAuctionPreset(models.Model):
    """Auktionstyp als Daten: Name, Typfarbe, Regeltext + 16-Achsen-Config."""

    name = models.CharField('Name', max_length=80)
    slug = models.SlugField(max_length=40, unique=True)
    color_hex = models.CharField(
        'Typfarbe',
        max_length=7,
        default='#ffd400',
        help_text='Hex-Farbe des Typs (nie Cyan — Cyan ist Funktionsfarbe).',
    )
    icon = models.CharField(max_length=40, blank=True, default='')
    rules_text = models.TextField(
        'Regeltext',
        blank=True,
        default='',
        help_text='Menschlich lesbare Regeln fürs Regelpanel der Detailseite.',
    )
    config = models.JSONField(
        default=dict,
        help_text='Belegung der 16 Regel-Achsen (validator.validate_config).',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Auktions-Preset'
        verbose_name_plural = 'Auktions-Presets'

    def __str__(self):
        return self.name


class ShowAuction(models.Model):
    """Eine konkrete Auktion — Config eingefroren, Spieler im Raum."""

    STATUS_DRAFT = 'draft'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_RUNNING = 'running'
    STATUS_SETTLED = 'settled'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Entwurf'),
        (STATUS_SCHEDULED, 'Geplant'),
        (STATUS_RUNNING, 'Läuft'),
        (STATUS_SETTLED, 'Zugeschlagen'),
        (STATUS_FAILED, 'Geplatzt'),
        (STATUS_CANCELLED, 'Abgebrochen'),
    ]
    ACTIVE_STATUSES = (STATUS_DRAFT, STATUS_SCHEDULED, STATUS_RUNNING)

    preset = models.ForeignKey(
        ShowAuctionPreset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auctions',
    )
    config_snapshot = models.JSONField(default=dict)
    type_name = models.CharField(max_length=80, default='', blank=True)
    color_hex = models.CharField(max_length=7, default='#ffd400')
    rules_text = models.TextField(blank=True, default='')

    player = models.ForeignKey(
        'game.Player',
        on_delete=models.PROTECT,
        related_name='show_auctions',
    )
    player_prev_pool_status = models.CharField(
        max_length=20,
        default='none',
        help_text='Pool-Status vor Raum-Eintritt — Rückweg bei failed/cancelled.',
    )
    hero_image = models.ImageField(
        upload_to=hero_upload_path, null=True, blank=True,
        help_text='Freigestelltes Hero-Bild (serverseitig via rembg).',
    )
    media_logo = models.ImageField(
        upload_to=logo_upload_path, null=True, blank=True,
        help_text='Medienlogo — wird NIE freigestellt, liegt auf dunkler Trägerfläche.',
    )

    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT,
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    start_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    market_value_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='MW des Spielers bei Anlage — Basis aller Prozent-Formeln.',
    )
    hidden_target = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Bereichsauktion: verborgene Korridor-Mitte (nie offenlegen).',
    )
    hidden_width = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Bereichsauktion: Korridor-Gesamtbreite in Euro.',
    )
    hold_step_index = models.PositiveSmallIntegerField(default=0)
    extension_count = models.PositiveIntegerField(default=0)
    endspurt_notified = models.BooleanField(default=False)

    conditions = models.JSONField(
        default=list, blank=True,
        help_text='Teilnahmebedingungen (Achse 12) — Liste von {art, …}.',
    )

    winner_club = models.ForeignKey(
        'game.Club',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='show_auction_wins',
    )
    winning_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    settled_at = models.DateTimeField(null=True, blank=True)
    fail_reason = models.CharField(max_length=200, blank=True, default='')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'ends_at']),
            models.Index(fields=['status', 'starts_at']),
        ]
        verbose_name = 'Show-Auktion'
        verbose_name_plural = 'Show-Auktionen'

    def __str__(self):
        return f'{self.type_name or "Auktion"} #{self.pk}: {self.player} [{self.get_status_display()}]'

    @property
    def cfg(self):
        return self.config_snapshot or {}


class ShowAuctionBid(models.Model):
    """Gebot eines Vereins. Verdeckte Gebote werden aktualisiert (eine Zeile),
    aufsteigende erzeugen je Erhöhung eine neue Zeile."""

    auction = models.ForeignKey(
        ShowAuction, on_delete=models.CASCADE, related_name='bids',
    )
    club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE, related_name='show_auction_bids',
    )
    manager = models.ForeignKey(
        'game.ManagerProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='show_auction_bids',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    is_active = models.BooleanField(default=True)
    is_leading = models.BooleanField(default=False)
    coin_charged = models.BooleanField(
        default=False,
        help_text='Eintrittsticket (Hoeneß-Coin) wurde mit diesem Gebot bezahlt.',
    )
    reservation_ref = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['auction', 'is_active']),
            models.Index(fields=['club', 'is_active']),
        ]
        verbose_name = 'Auktionsgebot'
        verbose_name_plural = 'Auktionsgebote'

    def __str__(self):
        return f'{self.club} bietet {self.amount:,.0f} € (Auktion #{self.auction_id})'


class ShowAuctionWatch(models.Model):
    """Beobachter einer Auktion — Quelle: eigenes Gebot oder manuell."""

    SOURCE_BID = 'bid'
    SOURCE_MANUAL = 'manual'
    SOURCE_CHOICES = [
        (SOURCE_BID, 'Gebot'),
        (SOURCE_MANUAL, 'Manuell'),
    ]

    auction = models.ForeignKey(
        ShowAuction, on_delete=models.CASCADE, related_name='watches',
    )
    club = models.ForeignKey(
        'game.Club', on_delete=models.CASCADE, related_name='show_auction_watches',
    )
    source = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default=SOURCE_MANUAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['auction', 'club'],
                name='unique_show_auction_watch',
            ),
        ]
        verbose_name = 'Auktions-Beobachtung'
        verbose_name_plural = 'Auktions-Beobachtungen'

    def __str__(self):
        return f'{self.club} beobachtet Auktion #{self.auction_id}'
