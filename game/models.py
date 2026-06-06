from django.contrib.staticfiles import finders
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from .tactics import (
    SQUAD_PRO,
    SQUAD_SCOPE_CHOICES,
    default_bench,
    default_formation,
    default_half_tactic,
    default_lineup,
    default_standards,
    default_substitutions,
    field_player_count,
    formation_code,
    validate_formation,
)


COUNTRY_FLAG_ASSETS = {
    'Afghanistan': {'code': 'AF'},
    'Ägypten': {'code': 'EG'},
    'Albanien': {'code': 'AL'},
    'Algerien': {'code': 'DZ', 'asset_id': '5'},
    'Andorra': {'code': 'AD'},
    'Angola': {'code': 'AO'},
    'Antigua und Barbuda': {'code': 'AG'},
    'Äquatorialguinea': {'code': 'GQ'},
    'Argentinien': {'code': 'AR'},
    'Armenien': {'code': 'AM'},
    'Aserbaidschan': {'code': 'AZ'},
    'Äthiopien': {'code': 'ET'},
    'Australien': {'code': 'AU'},
    'Bahamas': {'code': 'BS'},
    'Bahrain': {'code': 'BH'},
    'Bangladesch': {'code': 'BD'},
    'Barbados': {'code': 'BB'},
    'Belarus': {'code': 'BY'},
    'Belgien': {'code': 'BE'},
    'Belize': {'code': 'BZ'},
    'Benin': {'code': 'BJ'},
    'Bhutan': {'code': 'BT'},
    'Bolivien': {'code': 'BO'},
    'Bosnien und Herzegowina': {'code': 'BA'},
    'Bosnien-Herzegowina': {'code': 'BA'},
    'Botswana': {'code': 'BW'},
    'Brasilien': {'code': 'BR', 'asset_id': '1651'},
    'Brunei': {'code': 'BN'},
    'Bulgarien': {'code': 'BG'},
    'Burkina Faso': {'code': 'BF'},
    'Burundi': {'code': 'BI'},
    'Chile': {'code': 'CL'},
    'China': {'code': 'CN'},
    'Costa Rica': {'code': 'CR'},
    'Curacao': {'code': 'CW'},
    'Dänemark': {'code': 'DK'},
    'Deutschland': {'code': 'DE', 'asset_id': '771'},
    'Dominica': {'code': 'DM'},
    'Dominikanische Republik': {'code': 'DO'},
    'Dschibuti': {'code': 'DJ'},
    'Ecuador': {'code': 'EC'},
    'Elfenbeinküste': {'code': 'CI', 'asset_id': '24'},
    'El Salvador': {'code': 'SV'},
    'England': {'code': 'GB-ENG', 'asset_id': '765'},
    'Eritrea': {'code': 'ER'},
    'Estland': {'code': 'EE'},
    'Eswatini': {'code': 'SZ'},
    'Fidschi': {'code': 'FJ'},
    'Finnland': {'code': 'FI'},
    'Frankreich': {'code': 'FR', 'asset_id': '769'},
    'Guadeloupe': {'code': 'GP'},
    'Gabun': {'code': 'GA'},
    'Gambia': {'code': 'GM', 'asset_id': '20'},
    'Georgien': {'code': 'GE'},
    'Ghana': {'code': 'GH'},
    'Grenada': {'code': 'GD'},
    'Griechenland': {'code': 'GR'},
    'Guatemala': {'code': 'GT'},
    'Guinea': {'code': 'GN', 'asset_id': '22'},
    'Guinea-Bissau': {'code': 'GW', 'asset_id': '23'},
    'Guyana': {'code': 'GY'},
    'Haiti': {'code': 'HT'},
    'Honduras': {'code': 'HN'},
    'Indien': {'code': 'IN'},
    'Indonesien': {'code': 'ID'},
    'Irak': {'code': 'IQ'},
    'Iran': {'code': 'IR'},
    'Irland': {'code': 'IE', 'asset_id': '789'},
    'Island': {'code': 'IS'},
    'Israel': {'code': 'IL'},
    'Italien': {'code': 'IT', 'asset_id': '776'},
    'Jamaika': {'code': 'JM'},
    'Japan': {'code': 'JP', 'asset_id': '116'},
    'Jemen': {'code': 'YE'},
    'Jordanien': {'code': 'JO'},
    'Kambodscha': {'code': 'KH'},
    'Kamerun': {'code': 'CM'},
    'Kanada': {'code': 'CA', 'asset_id': '364'},
    'Kap Verde': {'code': 'CV'},
    'Kasachstan': {'code': 'KZ'},
    'Katar': {'code': 'QA'},
    'Kenia': {'code': 'KE'},
    'Kirgisistan': {'code': 'KG'},
    'Kiribati': {'code': 'KI'},
    'Kolumbien': {'code': 'CO', 'asset_id': '1653'},
    'Komoren': {'code': 'KM'},
    'Kongo (Demokratische Republik)': {'code': 'CD'},
    'Kongo (Republik)': {'code': 'CG'},
    'Kongo': {'code': 'CG'},
    'DR Kongo': {'code': 'CD'},
    'Korea (Nord)': {'code': 'KP'},
    'Kosovo': {'code': 'XK'},
    'Kroatien': {'code': 'HR', 'asset_id': '761'},
    'Kuba': {'code': 'CU'},
    'Kuwait': {'code': 'KW'},
    'Laos': {'code': 'LA'},
    'Lesotho': {'code': 'LS'},
    'Lettland': {'code': 'LV'},
    'Libanon': {'code': 'LB'},
    'Liberia': {'code': 'LR', 'asset_id': '27'},
    'Libyen': {'code': 'LY', 'asset_id': '28'},
    'Liechtenstein': {'code': 'LI'},
    'Litauen': {'code': 'LT'},
    'Luxemburg': {'code': 'LU'},
    'Madagaskar': {'code': 'MG'},
    'Malawi': {'code': 'MW'},
    'Malaysia': {'code': 'MY'},
    'Malediven': {'code': 'MV'},
    'Mali': {'code': 'ML'},
    'Malta': {'code': 'MT'},
    'Marokko': {'code': 'MA'},
    'Marshallinseln': {'code': 'MH'},
    'Mauretanien': {'code': 'MR'},
    'Mauritius': {'code': 'MU'},
    'Mexiko': {'code': 'MX'},
    'Mikronesien': {'code': 'FM'},
    'Moldau': {'code': 'MD'},
    'Monaco': {'code': 'MC'},
    'Mongolei': {'code': 'MN'},
    'Montenegro': {'code': 'ME'},
    'Mosambik': {'code': 'MZ'},
    'Myanmar': {'code': 'MM'},
    'Namibia': {'code': 'NA'},
    'Nauru': {'code': 'NR'},
    'Nepal': {'code': 'NP'},
    'Neuseeland': {'code': 'NZ'},
    'Nicaragua': {'code': 'NI'},
    'Niederlande': {'code': 'NL'},
    'Niger': {'code': 'NE'},
    'Nigeria': {'code': 'NG', 'asset_id': '38'},
    'Nordmazedonien': {'code': 'MK'},
    'Norwegen': {'code': 'NO', 'asset_id': '786'},
    'Oman': {'code': 'OM'},
    'Österreich': {'code': 'AT', 'asset_id': '755'},
    'Pakistan': {'code': 'PK'},
    'Palästina': {'code': 'PS'},
    'Palau': {'code': 'PW'},
    'Panama': {'code': 'PA'},
    'Papua-Neuguinea': {'code': 'PG'},
    'Paraguay': {'code': 'PY'},
    'Peru': {'code': 'PE'},
    'Philippinen': {'code': 'PH'},
    'Polen': {'code': 'PL'},
    'Portugal': {'code': 'PT', 'asset_id': '788'},
    'Ruanda': {'code': 'RW'},
    'Rumänien': {'code': 'RO'},
    'Russland': {'code': 'RU'},
    'Salomonen': {'code': 'SB'},
    'Sambia': {'code': 'ZM'},
    'Samoa': {'code': 'WS'},
    'San Marino': {'code': 'SM'},
    'São tomé und Príncipe': {'code': 'ST'},
    'Saudi-Arabien': {'code': 'SA'},
    'Schottland': {'code': 'GB-SCT'},
    'Schweden': {'code': 'SE', 'asset_id': '797'},
    'Schweiz': {'code': 'CH', 'asset_id': '798'},
    'Senegal': {'code': 'SN', 'asset_id': '41'},
    'Serbien': {'code': 'RS', 'asset_id': '802'},
    'Seychellen': {'code': 'SC'},
    'Sierra Leone': {'code': 'SL'},
    'Simbabwe': {'code': 'ZW'},
    'Singapur': {'code': 'SG'},
    'Slowakei': {'code': 'SK'},
    'Slowenien': {'code': 'SI'},
    'Somalia': {'code': 'SO'},
    'Spanien': {'code': 'ES'},
    'Sri Lanka': {'code': 'LK'},
    'St. Kitts und Nevis': {'code': 'KN'},
    'St. Lucia': {'code': 'LC'},
    'St. Vincent und die Grenadinen': {'code': 'VC'},
    'Südafrika': {'code': 'ZA'},
    'Sudan': {'code': 'SD'},
    'Südkorea': {'code': 'KR', 'asset_id': '135'},
    'Südsudan': {'code': 'SS'},
    'Suriname': {'code': 'SR'},
    'Syrien': {'code': 'SY'},
    'Tadschikistan': {'code': 'TJ'},
    'Tansania': {'code': 'TZ'},
    'Thailand': {'code': 'TH'},
    'Timor-Leste': {'code': 'TL'},
    'Togo': {'code': 'TG'},
    'Tonga': {'code': 'TO'},
    'Trinidad und Tobago': {'code': 'TT'},
    'Tschad': {'code': 'TD'},
    'Tschechien': {'code': 'CZ'},
    'Tunesien': {'code': 'TN'},
    'Türkei': {'code': 'TR', 'asset_id': '799'},
    'Turkmenistan': {'code': 'TM'},
    'Tuvalu': {'code': 'TV'},
    'Uganda': {'code': 'UG'},
    'Ukraine': {'code': 'UA'},
    'Ungarn': {'code': 'HU'},
    'Uruguay': {'code': 'UY'},
    'Usbekistan': {'code': 'UZ'},
    'Vanuatu': {'code': 'VU'},
    'Venezuela': {'code': 'VE'},
    'Vereinigte Arabische Emirate': {'code': 'AE'},
    'Vereinigte Staaten': {'code': 'US', 'asset_id': '390'},
    'Vereinigtes Königreich': {'code': 'GB'},
    'Vietnam': {'code': 'VN'},
    'Wales': {'code': 'GB-WLS'},
    'Zentralafrikanische Republik': {'code': 'CF'},
    'Zypern': {'code': 'CY'},
}


STRENGTH_DEFAULT_BASE = Decimal('40.00')
STRENGTH_QUANT = Decimal('0.01')
SNAPSHOT_HISTORY_LIMIT = 10


def strength_decimal(value):
    return Decimal(str(value)).quantize(STRENGTH_QUANT)


def prune_snapshot_history(model, filters, limit=SNAPSHOT_HISTORY_LIMIT):
    stale_ids = list(
        model.objects.filter(**filters).order_by(
            '-recorded_at',
            '-id',
        ).values_list('id', flat=True)[limit:]
    )
    if stale_ids:
        model.objects.filter(id__in=stale_ids).delete()


class DataSource(models.Model):
    CODE_TRANSFERMARKT = 'TM'
    CODE_FMINSIDE = 'FM'
    CODE_SOFIFA = 'SOFIFA'
    CODE_API_FOOTBALL = 'API_FOOTBALL'
    CODE_WEBSOCCER = 'WSC'
    CODE_CHOICES = [
        (CODE_TRANSFERMARKT, 'Transfermarkt'),
        (CODE_FMINSIDE, 'FMInside'),
        (CODE_SOFIFA, 'SoFIFA'),
        (CODE_API_FOOTBALL, 'API-Football'),
        (CODE_WEBSOCCER, 'Websoccer'),
    ]

    code = models.CharField(max_length=40, unique=True, choices=CODE_CHOICES)
    name = models.CharField(max_length=100)
    base_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Datenquelle'
        verbose_name_plural = 'Datenquellen'

    def __str__(self):
        return self.name


class StrengthFormulaSettings(models.Model):
    name = models.CharField(max_length=100, default='Standard')
    is_active = models.BooleanField(default=True)
    rating_modifier_factor = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text='Faktor fuer (Spieler-Rating - Liga-Medianrating).',
    )
    default_league_median_rating = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('6.80'),
        help_text='Fallback, bis der Median dynamisch aus Massendaten berechnet wird.',
    )
    default_freshness = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
        help_text='Wird genutzt, wenn noch kein Spieler-Frischewert gepflegt ist.',
    )
    notes = models.TextField(
        blank=True,
        help_text='Balancing-Notizen, z. B. Peak-Verteilung oder offene Tests.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Spielstaerke-Modifikator'
        verbose_name_plural = 'Spielstaerke-Modifikatoren'

    def __str__(self):
        return self.name

    @classmethod
    def active(cls):
        return cls.objects.filter(is_active=True).order_by('id').first()


class StrengthModifierRule(models.Model):
    CATEGORY_MINUTES = 'minutes'
    CATEGORY_FRESHNESS = 'freshness'
    CATEGORY_CHOICES = [
        (CATEGORY_MINUTES, 'Minutenquote'),
        (CATEGORY_FRESHNESS, 'Frische'),
    ]

    settings = models.ForeignKey(
        StrengthFormulaSettings,
        on_delete=models.CASCADE,
        related_name='modifier_rules',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    label = models.CharField(max_length=100)
    min_value = models.DecimalField(max_digits=6, decimal_places=2)
    max_value = models.DecimalField(max_digits=6, decimal_places=2)
    modifier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text='Staerkepunkte. Bei Frische sind Abzuege negativ.',
    )
    risk_label = models.CharField(
        max_length=80,
        blank=True,
        help_text='Nur fuer Frische relevant, z. B. leichtes Risiko.',
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = [
            'category',
            'sort_order',
            '-min_value',
        ]
        verbose_name = 'Spielstaerke-Regel'
        verbose_name_plural = 'Spielstaerke-Regeln'

    def __str__(self):
        return f'{self.get_category_display()} {self.min_value}-{self.max_value}: {self.modifier}'

    def matches(self, value):
        value = Decimal(value)
        return self.min_value <= value <= self.max_value


class League(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    api_football_id = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True,
    )
    strength_coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        help_text='Liga-Koeffizient fuer Form- und Leistungsgewichtung.',
    )
    coefficient_source = models.CharField(
        max_length=100,
        blank=True,
        help_text='z. B. UEFA association coefficient oder interne Einstufung.',
    )

    def __str__(self):
        return self.name


class Club(models.Model):
    fm_inside_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True
    )
    api_football_id = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20)
    founded_year = models.IntegerField()

    budget = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    fan_popularity = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name='Fanbeliebtheit (1–100)',
        help_text='Wie beliebt ist der Verein bei Fans? Beeinflusst die Stadionauslastung.',
    )

    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE
    )

    managed_by = models.OneToOneField(
        'ManagerProfile',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_club',
        verbose_name='Aktueller Trainer',
        help_text=(
            'Welcher Manager leitet diesen Verein gerade? '
            'Bitte nicht direkt bearbeiten — stattdessen im Vereins-Admin '
            '"Trainer zuweisen" oder "Trainer entlassen" nutzen, '
            'damit die Karrierekarte automatisch aktualisiert wird.'
        ),
    )

    def __str__(self):
        return self.name

    @property
    def crest_static_path(self):
        if not self.fm_inside_id:
            return ''

        for ext in ('png', 'svg'):
            path = f'game/images/crests/{self.fm_inside_id}.{ext}'
            if finders.find(path):
                return path
        return ''

    @property
    def kit_static_paths(self):
        if not self.fm_inside_id:
            return []

        kits = []
        for label, suffix in (('Heim', 'home'), ('Auswärts', 'away'), ('Third', 'third')):
            path = ''
            for ext in ('svg', 'png'):
                candidate = f'game/images/kits/{self.fm_inside_id}_{suffix}.{ext}'
                if finders.find(candidate):
                    path = candidate
                    break
            kits.append({'label': label, 'path': path})
        return kits


class Stadium(models.Model):
    club = models.OneToOneField(
        Club,
        on_delete=models.CASCADE,
        related_name='stadium',
    )
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=100)
    lawn_quality = models.PositiveSmallIntegerField(
        default=85,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name='Rasenqualität (1–100)',
    )

    nord_standing = models.PositiveIntegerField(default=0, verbose_name='Nord – Stehplätze')
    nord_seating  = models.PositiveIntegerField(default=0, verbose_name='Nord – Sitzplätze')
    nord_vip      = models.PositiveIntegerField(default=0, verbose_name='Nord – VIP')

    ost_standing  = models.PositiveIntegerField(default=0, verbose_name='Ost – Stehplätze')
    ost_seating   = models.PositiveIntegerField(default=0, verbose_name='Ost – Sitzplätze')
    ost_vip       = models.PositiveIntegerField(default=0, verbose_name='Ost – VIP')

    sued_standing = models.PositiveIntegerField(default=0, verbose_name='Süd – Stehplätze')
    sued_seating  = models.PositiveIntegerField(default=0, verbose_name='Süd – Sitzplätze')
    sued_vip      = models.PositiveIntegerField(default=0, verbose_name='Süd – VIP')

    west_standing = models.PositiveIntegerField(default=0, verbose_name='West – Stehplätze')
    west_seating  = models.PositiveIntegerField(default=0, verbose_name='West – Sitzplätze')
    west_vip      = models.PositiveIntegerField(default=0, verbose_name='West – VIP')

    price_standing = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('15.00'),
        verbose_name='Ticketpreis Steh (€)',
    )
    price_seating = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('35.00'),
        verbose_name='Ticketpreis Sitz (€)',
    )
    price_vip = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('120.00'),
        verbose_name='Ticketpreis VIP (€)',
    )

    # Stadionumfeld-Einrichtungen (0 = nicht vorhanden, max 3)
    nlz_level      = models.PositiveSmallIntegerField(default=0, verbose_name='NLZ Stufe')
    medizin_level  = models.PositiveSmallIntegerField(default=0, verbose_name='Medizin Stufe')
    training_level = models.PositiveSmallIntegerField(default=0, verbose_name='Trainingsgelände Stufe')
    office_level   = models.PositiveSmallIntegerField(default=0, verbose_name='Geschäftsstelle Stufe')

    @property
    def capacity_total(self):
        return (
            self.nord_standing + self.nord_seating + self.nord_vip +
            self.ost_standing  + self.ost_seating  + self.ost_vip  +
            self.sued_standing + self.sued_seating + self.sued_vip +
            self.west_standing + self.west_seating + self.west_vip
        )

    @property
    def capacity_standing(self):
        return self.nord_standing + self.ost_standing + self.sued_standing + self.west_standing

    @property
    def capacity_seating(self):
        return self.nord_seating + self.ost_seating + self.sued_seating + self.west_seating

    @property
    def capacity_vip(self):
        return self.nord_vip + self.ost_vip + self.sued_vip + self.west_vip

    def __str__(self):
        return f'{self.name} ({self.club.name})'

    class Meta:
        verbose_name = 'Stadion'
        verbose_name_plural = 'Stadien'


class StadiumExpansion(models.Model):
    STAND_CHOICES = [
        ('NORD', 'Nordkurve'),
        ('OST',  'Osttribüne'),
        ('SUED', 'Südkurve'),
        ('WEST', 'Westtribüne'),
    ]
    SEAT_TYPE_CHOICES = [
        ('STEH', 'Stehplatz'),
        ('SITZ', 'Sitzplatz'),
        ('VIP',  'VIP'),
    ]

    stadium    = models.ForeignKey(
        Stadium,
        on_delete=models.CASCADE,
        related_name='expansions',
    )
    stand      = models.CharField(max_length=4, choices=STAND_CHOICES)
    seat_type  = models.CharField(max_length=4, choices=SEAT_TYPE_CHOICES)
    seats_added = models.PositiveIntegerField()
    cost       = models.DecimalField(max_digits=14, decimal_places=2)
    ordered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Stadionausbau'
        verbose_name_plural = 'Stadionausbauten'
        ordering = ['-ordered_at']

    def __str__(self):
        return (
            f'{self.stadium.name}: +{self.seats_added} {self.get_seat_type_display()} '
            f'({self.get_stand_display()})'
        )


class MatchdayRevenue(models.Model):
    """
    Protokolliert Stadioneinnahmen nach einem Heimspiel.
    Wird bei jedem Heimspiel automatisch berechnet und dem Vereinsbudget gutgeschrieben.
    """

    stadium = models.ForeignKey(
        'Stadium',
        on_delete=models.CASCADE,
        related_name='revenue_entries',
        verbose_name='Stadion',
    )
    match_result = models.OneToOneField(
        'MatchResult',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matchday_revenue',
        verbose_name='Spielergebnis',
    )
    match_label = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Spielbezeichnung',
    )
    competition_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='Wettbewerb',
    )
    auslastung_pct = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        verbose_name='Auslastung (%)',
        help_text='Tatsächliche Auslastung dieses Spieltags in Prozent (0–100).',
    )
    attendance = models.PositiveIntegerField(
        default=0,
        verbose_name='Zuschauer',
    )
    revenue_standing = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Einnahmen Stehplätze (€)',
    )
    revenue_seating = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Einnahmen Sitzplätze (€)',
    )
    revenue_vip = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Einnahmen VIP (€)',
    )
    revenue_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Gesamteinnahmen (€)',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Verbucht am',
    )

    class Meta:
        verbose_name = 'Spieltags-Einnahmen'
        verbose_name_plural = 'Spieltags-Einnahmen'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'{self.stadium.name} – {self.match_label or self.competition_name}: '
            f'{self.revenue_total:,.0f} € ({self.auslastung_pct} %)'
        )


class ClubPublicProfile(models.Model):
    club = models.OneToOneField(
        Club,
        on_delete=models.CASCADE,
        related_name='public_profile',
    )
    stadium_name = models.CharField(max_length=120, blank=True)
    stadium_capacity = models.PositiveIntegerField(default=0)
    average_attendance = models.PositiveIntegerField(default=0)
    city_name = models.CharField(max_length=120, blank=True)
    city_country = models.CharField(max_length=100, blank=True)
    map_lat = models.FloatField(null=True, blank=True, verbose_name='Breitengrad (Karte)')
    map_lng = models.FloatField(null=True, blank=True, verbose_name='Längengrad (Karte)')
    stadium_image_static_path = models.CharField(max_length=240, blank=True)
    city_image_static_path = models.CharField(max_length=240, blank=True)
    partner_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='partnered_public_profiles',
    )

    class Meta:
        verbose_name = 'Oeffentliches Vereinsprofil'
        verbose_name_plural = 'Oeffentliche Vereinsprofile'

    def __str__(self):
        return f'Profil {self.club}'


class ClubTrophy(models.Model):
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='public_trophies',
    )
    competition_name = models.CharField(max_length=120)
    count = models.PositiveSmallIntegerField(default=1)
    trophy_asset_id = models.CharField(max_length=80, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'competition_name']
        verbose_name = 'Vereinstitel'
        verbose_name_plural = 'Vereinstitel'

    # All FM Inside asset IDs below were visually verified against the badge
    # image files in game/static/game/images/trophies/ on 2026-06-02.
    # Each image was rendered and cross-checked against the known competition
    # trophy/badge.  No incorrect mappings were found; all IDs are confirmed.
    COMPETITION_DEFAULT_ASSETS = {
        # Continental / global — visually verified
        'Intercontinental':    'international-cup-1',
        'Champions League':    '1301394',
        'Copa Libertadores':   '1002136',   # confirmed: tall silver Copa Libertadores trophy
        'Europa League':       '1001960',   # confirmed: Europa League cup
        'Klub-WM':             '1001959',
        'FIFA Club World Cup': '1001959',
        'Club World Cup':      '1001959',
        # Germany — visually verified
        'Bundesliga':          '22',
        'DFB-Pokal':           '1301410',
        'DFL-Supercup':        '1301397',
        'Supercup':            '1301397',
        'DFB-Ligapokal':       '100',
        # England — visually verified
        'Premier League':      '1301393',   # confirmed: crown-topped trophy with lion handles
        'FA Cup':              '1301406',   # confirmed: silver cup with round handles
        # Spain — visually verified
        'La Liga':             '1301395',   # confirmed: silver La Liga trophy
        'Copa del Rey':        '1301417',   # confirmed: ornate golden cup
        'Supercopa de España': '1301419',   # confirmed
        # Italy — visually verified
        'Serie A':             '1301398',   # confirmed: distinctive golden sphere trophy
        'Coppa Italia':        '1301407',   # confirmed: ornate silver cup
        # Netherlands — visually verified
        'Eredivisie':          '1301412',   # confirmed: golden Eredivisie Schaal bowl
        'KNVB Cup':            '1301411',   # confirmed
        # Portugal — visually verified
        'Primeira Liga':       '1301403',   # confirmed
        'Taça de Portugal':    '1301404',   # confirmed: distinctive Portuguese cup badge
        # Serbia — visually verified
        'Superliga Srbije':    '1301427',   # confirmed: ornate league trophy
        'Kup Srbije':          '1301426',   # confirmed: Serbian cup competition badge
        # South America — domestic (no confirmed FM Inside badge IDs available;
        # generic competition-type assets are used as the best visual fallback)
        'Brasileirão':         'national championship 1',
        'Copa do Brasil':      'national cup 1',
        'Taça Brasil':         'national cup 1',
        'Primera División':    'national championship 1',
        'Copa Argentina':      'national cup 1',
        'Copa Uruguay':        'national cup 1',
        'División de Honor':   'national championship 1',
        'Copa Paraguay':       'national cup 1',
    }

    def save(self, *args, **kwargs):
        if not self.trophy_asset_id and self.competition_name in self.COMPETITION_DEFAULT_ASSETS:
            self.trophy_asset_id = self.COMPETITION_DEFAULT_ASSETS[self.competition_name]
        super().save(*args, **kwargs)

    @property
    def trophy_static_path(self):
        from .player_assets import get_cached_trophy_static_path

        return get_cached_trophy_static_path(self.trophy_asset_id)

    def __str__(self):
        return f'{self.club} - {self.competition_name}'


class ClubProfileMatch(models.Model):
    KIND_NEXT = 'next'
    KIND_LAST = 'last'
    KIND_CHOICES = [
        (KIND_NEXT, 'Naechstes Spiel'),
        (KIND_LAST, 'Letztes Spiel'),
    ]

    RESULT_WIN = 'SIEG'
    RESULT_DRAW = 'UNENTSCHIEDEN'
    RESULT_LOSS = 'NIEDERLAGE'
    RESULT_CHOICES = [
        (RESULT_WIN, 'Sieg'),
        (RESULT_DRAW, 'Unentschieden'),
        (RESULT_LOSS, 'Niederlage'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='public_profile_matches',
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    competition_name = models.CharField(max_length=120)
    matchday_label = models.CharField(max_length=80)
    date_label = models.CharField(max_length=80, blank=True)
    time_label = models.CharField(max_length=40, blank=True)
    stadium_name = models.CharField(max_length=120, blank=True)
    home_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='home_public_profile_matches',
    )
    away_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='away_public_profile_matches',
    )
    home_goals = models.PositiveSmallIntegerField(null=True, blank=True)
    away_goals = models.PositiveSmallIntegerField(null=True, blank=True)
    result_label = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        blank=True,
    )
    scorers = models.JSONField(default=list, blank=True)
    nt_nationality = models.CharField(
        'NT-Nationalität',
        max_length=60,
        blank=True,
        help_text=(
            'Die Nationalität für NT-Wettbewerbe (z. B. "Deutschland"). '
            'Wird verwendet, um das richtige Konföderation-Badge anzuzeigen.'
        ),
    )

    class Meta:
        ordering = ['kind', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'kind'],
                name='unique_club_public_profile_match_kind',
            ),
        ]
        verbose_name = 'Vereinsprofil-Spiel'
        verbose_name_plural = 'Vereinsprofil-Spiele'

    def __str__(self):
        return f'{self.club} - {self.get_kind_display()}'


class MatchResult(models.Model):
    RESULT_WIN = 'SIEG'
    RESULT_DRAW = 'UNENTSCHIEDEN'
    RESULT_LOSS = 'NIEDERLAGE'
    RESULT_CHOICES = [
        (RESULT_WIN, 'Sieg'),
        (RESULT_DRAW, 'Unentschieden'),
        (RESULT_LOSS, 'Niederlage'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='match_results',
        verbose_name='Verein',
    )
    season = models.CharField(
        max_length=20,
        blank=True,
        help_text='Saison, z. B. "2023/24"',
        verbose_name='Saison',
    )
    competition_name = models.CharField(
        max_length=120,
        verbose_name='Wettbewerb',
    )
    matchday_label = models.CharField(
        max_length=80,
        blank=True,
        verbose_name='Spieltag',
    )
    date_label = models.CharField(
        max_length=80,
        blank=True,
        verbose_name='Datum',
    )
    home_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='home_match_results',
        verbose_name='Heimverein',
    )
    away_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='away_match_results',
        verbose_name='Auswärtsverein',
    )
    home_goals = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Heimtore')
    away_goals = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Auswärtstore')
    result_label = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        verbose_name='Ergebnis',
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text='Niedrigere Zahlen erscheinen zuerst (chronologische Reihenfolge).',
        verbose_name='Sortierreihenfolge',
    )

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = 'Spielergebnis'
        verbose_name_plural = 'Spielergebnisse'

    def __str__(self):
        hg = self.home_goals if self.home_goals is not None else '?'
        ag = self.away_goals if self.away_goals is not None else '?'
        home = self.home_club.name if self.home_club else '?'
        away = self.away_club.name if self.away_club else '?'
        return f'{home} {hg}:{ag} {away} ({self.season})'


class TacticSetup(models.Model):
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='tactic_setups',
    )
    squad_scope = models.CharField(
        max_length=12,
        choices=SQUAD_SCOPE_CHOICES,
        default=SQUAD_PRO,
    )
    formation = models.JSONField(default=default_formation, blank=True)
    lineup = models.JSONField(default=default_lineup, blank=True)
    bench = models.JSONField(default=default_bench, blank=True)
    standards = models.JSONField(default=default_standards, blank=True)
    substitutions = models.JSONField(default=default_substitutions, blank=True)
    first_half = models.JSONField(default=default_half_tactic, blank=True)
    second_half = models.JSONField(default=default_half_tactic, blank=True)
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'squad_scope'],
                name='unique_club_tactic_setup_scope',
            ),
        ]
        ordering = ['club__name', 'squad_scope']
        verbose_name = 'Taktik'
        verbose_name_plural = 'Taktiken'

    def clean(self):
        super().clean()
        validate_formation(self.formation)
        if len(self.bench or []) > 7:
            raise ValidationError('Es sind maximal 7 Bankspieler erlaubt.')
        if len(self.substitutions or []) > 5:
            raise ValidationError('Es sind maximal 5 Wechsel erlaubt.')

    @property
    def formation_code(self):
        return formation_code(self.formation)

    @property
    def field_player_count(self):
        return field_player_count(self.formation)

    def __str__(self):
        return f'{self.club} - {self.get_squad_scope_display()} - {self.formation_code}'


class TacticTemplate(models.Model):
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='tactic_templates',
    )
    squad_scope = models.CharField(
        max_length=12,
        choices=SQUAD_SCOPE_CHOICES,
        default=SQUAD_PRO,
    )
    name = models.CharField(max_length=80)
    formation = models.JSONField(default=default_formation, blank=True)
    lineup = models.JSONField(default=default_lineup, blank=True)
    bench = models.JSONField(default=default_bench, blank=True)
    standards = models.JSONField(default=default_standards, blank=True)
    substitutions = models.JSONField(default=default_substitutions, blank=True)
    first_half = models.JSONField(default=default_half_tactic, blank=True)
    second_half = models.JSONField(default=default_half_tactic, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'squad_scope', 'name'],
                name='unique_club_tactic_template_scope_name',
            ),
        ]
        ordering = ['club__name', 'squad_scope', 'name']
        verbose_name = 'Taktikvorlage'
        verbose_name_plural = 'Taktikvorlagen'

    def clean(self):
        super().clean()
        validate_formation(self.formation)
        if len(self.bench or []) > 7:
            raise ValidationError('Es sind maximal 7 Bankspieler erlaubt.')
        if len(self.substitutions or []) > 5:
            raise ValidationError('Es sind maximal 5 Wechsel erlaubt.')
        if self.club_id and self.squad_scope:
            existing = TacticTemplate.objects.filter(
                club_id=self.club_id,
                squad_scope=self.squad_scope,
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.count() >= 10:
                raise ValidationError('Es sind maximal 10 Taktikvorlagen pro Bereich erlaubt.')

    @property
    def formation_code(self):
        return formation_code(self.formation)

    def __str__(self):
        return f'{self.club} - {self.get_squad_scope_display()} - {self.name}'


class ClubNewsItem(models.Model):
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='public_news',
    )
    title = models.CharField(max_length=160)
    published_at = models.DateField(default=timezone.localdate)
    thumbnail_static_path = models.CharField(max_length=240, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', '-published_at', '-id']
        verbose_name = 'Vereinsnews'
        verbose_name_plural = 'Vereinsnews'

    def __str__(self):
        return f'{self.club} - {self.title}'


class Player(models.Model):
    POSITION_CHOICES = [
        ('TW', 'TW'),
        ('IV', 'IV'),
        ('LV', 'LV'),
        ('RV', 'RV'),
        ('LOV', 'LOV'),
        ('ROV', 'ROV'),
        ('DM', 'DM'),
        ('ZM', 'ZM'),
        ('LM', 'LM'),
        ('RM', 'RM'),
        ('LOM', 'LOM'),
        ('ROM', 'ROM'),
        ('OM', 'OM'),
        ('LF', 'LF'),
        ('RF', 'RF'),
        ('ST', 'ST'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    wsc_player_id = models.CharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        help_text='Stabile Websoccer-ID fuer Assets, Graphen und externe Zuordnung.',
    )
    fm_inside_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True
    )
    transfermarkt_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True
    )
    api_football_id = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True,
    )
    transfermarkt_profile_url = models.URLField(blank=True)
    transfermarkt_market_value_url = models.URLField(blank=True)
    date_of_birth = models.DateField(
        null=True,
        blank=True
    )
    nationalities = models.CharField(
        max_length=150,
        blank=True
    )
    nt_nationality = models.CharField(
        'Nationalmannschafts-Nation',
        max_length=60,
        blank=True,
        help_text=(
            'Die Nation, für die der Spieler international registriert ist. '
            'Wird für das NT-Badge auf dem Spielerprofil verwendet. '
            'Leer lassen, um automatisch die erste Nationalität zu verwenden.'
        ),
    )
    age = models.IntegerField()
    height_cm = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Koerpergroesse in Zentimetern.',
    )
    strong_foot = models.CharField(
        max_length=10,
        blank=True,
        choices=[
            ('left', 'Links'),
            ('right', 'Rechts'),
            ('both', 'Beidfuss'),
        ],
        help_text='Staerkerer Fuss des Spielers.',
    )
    shirt_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Trikotnummer des Spielers.',
    )

    position = models.CharField(
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    primary_position = models.CharField(
        max_length=100,
        choices=POSITION_CHOICES,
        blank=True
    )
    source_positions = models.CharField(
        max_length=100,
        choices=POSITION_CHOICES,
        blank=True
    )
    main_position_1 = models.CharField(
        'HP 1',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    main_position_2 = models.CharField(
        'HP 2',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    main_position_3 = models.CharField(
        'HP 3',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    secondary_position_1 = models.CharField(
        'NP 1',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    secondary_position_2 = models.CharField(
        'NP 2',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )
    secondary_position_3 = models.CharField(
        'NP 3',
        max_length=10,
        choices=POSITION_CHOICES,
        blank=True
    )

    potential = models.IntegerField(default=50)

    market_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )
    salary_per_match = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    contract_until = models.DateField(
        null=True,
        blank=True
    )

    club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    real_life_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        related_name='real_life_players',
        null=True,
        blank=True,
        help_text='Aktueller realer Verein, getrennt vom Websoccer-Verein.'
    )
    ws_injury_type = models.CharField(
        max_length=120,
        blank=True,
        help_text='Nur Websoccer-Verletzung, z. B. Muskelverletzung.'
    )
    ws_injury_days_remaining = models.PositiveSmallIntegerField(default=0)
    ws_suspension_reason = models.CharField(
        max_length=120,
        blank=True,
        help_text='Nur Websoccer-Sperre, z. B. Rotsperre.'
    )
    ws_suspension_matches_remaining = models.PositiveSmallIntegerField(default=0)

    LOAN_STATUS_CHOICES = [
        ('none', 'Kein Leihverhältnis'),
        ('loaned_in', 'Geliehen'),
        ('loaned_out', 'Verliehen'),
    ]
    loan_status = models.CharField(
        'Leihstatus',
        max_length=12,
        choices=LOAN_STATUS_CHOICES,
        default='none',
        blank=True,
        help_text='Geliehen = im Verein aktiv, gehört einem anderen Verein. '
                  'Verliehen = gehört diesem Verein, spielt aktuell woanders.',
    )
    loan_partner_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        related_name='loan_partner_players',
        null=True,
        blank=True,
        help_text='Der andere Verein des Leihgeschäfts (Stamm- bzw. Leihverein).',
    )
    loan_until = models.DateField(
        'Leihe bis',
        null=True,
        blank=True,
    )
    is_on_transfer_list = models.BooleanField(
        'Auf Transferliste',
        default=False,
    )
    is_on_loan_list = models.BooleanField(
        'Auf Leihliste',
        default=False,
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_loaned_in(self):
        return self.loan_status == 'loaned_in'

    @property
    def is_loaned_out(self):
        return self.loan_status == 'loaned_out'

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def portrait_static_path(self):
        if not self.fm_inside_id:
            return 'game/images/default_player.svg'

        for extension in ('png', 'svg'):
            path = f'game/images/players/{self.fm_inside_id}.{extension}'
            if finders.find(path):
                return path

        return 'game/images/default_player.svg'

    @property
    def profile_portrait_static_path(self):
        from .player_assets import get_cached_profile_portrait_static_path

        return get_cached_profile_portrait_static_path(self)

    @property
    def strong_foot_label(self):
        return dict(self._meta.get_field('strong_foot').choices).get(
            self.strong_foot,
            '-',
        )

    @property
    def nationality_badges(self):
        countries = [
            country.strip()
            for country in self.nationalities.split(',')
            if country.strip()
        ]

        return [
            {
                'name': country,
                'code': COUNTRY_FLAG_ASSETS.get(country, {'code': country[:2].upper()})['code'],
                'flag_url': (
                    f"https://flagcdn.com/{COUNTRY_FLAG_ASSETS[country]['code'].lower()}.svg"
                ) if country in COUNTRY_FLAG_ASSETS else '',
            }
            for country in countries
        ]

    @property
    def primary_nation_crest(self):
        countries = [
            country.strip()
            for country in self.nationalities.split(',')
            if country.strip()
        ]
        if not countries:
            return {}

        country = countries[0]
        nation_asset = COUNTRY_FLAG_ASSETS.get(country)
        if not nation_asset:
            return {}

        from .player_assets import get_cached_nation_static_path

        static_path = get_cached_nation_static_path(nation_asset.get('asset_id', ''))
        if not static_path:
            return {}

        return {
            'name': country,
            'static_path': static_path,
        }

    @property
    def main_positions(self):
        return [
            position
            for position in [
                self.main_position_1,
                self.main_position_2,
                self.main_position_3,
            ]
            if position
        ]

    @property
    def secondary_positions(self):
        return [
            position
            for position in [
                self.secondary_position_1,
                self.secondary_position_2,
                self.secondary_position_3,
            ]
            if position
        ]

    @property
    def all_position_codes(self):
        return self.main_positions + self.secondary_positions

    @property
    def is_ws_injured(self):
        return bool(self.ws_injury_type and self.ws_injury_days_remaining > 0)

    @property
    def is_ws_suspended(self):
        return bool(
            self.ws_suspension_reason and self.ws_suspension_matches_remaining > 0
        )

    def get_source_rating(self, source):
        prefetched_ratings = getattr(
            self,
            '_prefetched_objects_cache',
            {},
        ).get('source_ratings')

        if prefetched_ratings is not None:
            for rating in prefetched_ratings:
                if rating.source == source:
                    return rating

            return None

        return self.source_ratings.filter(source=source).first()

    @property
    def ea_source_rating(self):
        return self.get_source_rating(PlayerSourceRating.SOURCE_EA)

    @property
    def fm_source_rating(self):
        return self.get_source_rating(PlayerSourceRating.SOURCE_FM)

    @property
    def source_rating_count(self):
        return sum(
            1
            for rating in [self.ea_source_rating, self.fm_source_rating]
            if rating
        )

    @property
    def source_base_quality(self):
        if self.source_rating_count == 2:
            return 'complete'

        if self.source_rating_count == 1:
            return 'partial'

        return 'default'

    @property
    def source_base_quality_label(self):
        labels = {
            'complete': 'EA + FM',
            'partial': 'nur eine Quelle',
            'default': 'Default 40.00',
        }
        return labels[self.source_base_quality]

    @property
    def uses_default_base_strength(self):
        return self.source_base_quality == 'default'

    @property
    def calculated_base_strength(self):
        ea_rating = self.ea_source_rating
        fm_rating = self.fm_source_rating

        if ea_rating and fm_rating:
            return strength_decimal(ea_rating.rating + fm_rating.rating)

        if ea_rating:
            return strength_decimal(ea_rating.rating * 2)

        if fm_rating:
            return strength_decimal(fm_rating.rating * 2)

        return STRENGTH_DEFAULT_BASE

    @property
    def calculated_potential_strength(self):
        ea_rating = self.ea_source_rating
        fm_rating = self.fm_source_rating

        ea_potential = ea_rating.potential if ea_rating else None
        fm_potential = fm_rating.potential if fm_rating else None

        if ea_potential is not None and fm_potential is not None:
            return strength_decimal(ea_potential + fm_potential)

        if ea_potential is not None:
            return strength_decimal(ea_potential * 2)

        if fm_potential is not None:
            return strength_decimal(fm_potential * 2)

        if self.uses_default_base_strength:
            return None

        return self.calculated_base_strength

    @property
    def source_strength_explanation(self):
        ea_rating = self.ea_source_rating
        fm_rating = self.fm_source_rating
        lines = []

        if ea_rating:
            lines.append(f'EA Staerke: {ea_rating.rating}')
        else:
            lines.append('EA Staerke fehlt')

        if fm_rating:
            lines.append(f'FM Staerke: {fm_rating.rating}')
        else:
            lines.append('FM Staerke fehlt')

        if self.calculated_base_strength is not None:
            if ea_rating and fm_rating:
                lines.append(
                    f'Base = EA + FM = {self.calculated_base_strength:.2f}'
                )
            elif ea_rating:
                lines.append(
                    f'Base = EA * 2 = {self.calculated_base_strength:.2f}'
                )
            elif fm_rating:
                lines.append(
                    f'Base = FM * 2 = {self.calculated_base_strength:.2f}'
                )
            else:
                lines.append('Base = Default = 40.00')
        else:
            lines.append('Base kann erst mit EA- und FM-Wert berechnet werden')

        if ea_rating and ea_rating.potential is not None:
            lines.append(f'EA Potential: {ea_rating.potential}')
        else:
            lines.append('EA Potential fehlt')

        if fm_rating and fm_rating.potential is not None:
            lines.append(f'FM Potential: {fm_rating.potential}')
        else:
            lines.append('FM Potential fehlt')

        if self.calculated_potential_strength is not None:
            lines.append(
                'Potential-Ceiling = '
                f'{self.calculated_potential_strength:.2f}'
            )

        return ' | '.join(lines)


class PlayerExternalId(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='external_ids',
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='player_external_ids',
    )
    external_id = models.CharField(max_length=120)
    profile_url = models.URLField(blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['player__last_name', 'player__first_name', 'source__name']
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'external_id'],
                name='unique_external_player_id_per_source',
            ),
            models.UniqueConstraint(
                fields=['player', 'source'],
                name='unique_player_external_id_per_source',
            ),
        ]
        verbose_name = 'Spieler-ID'
        verbose_name_plural = 'Spieler-IDs'

    def __str__(self):
        return f'{self.player} - {self.source.code}: {self.external_id}'


class PlayerSourceRating(models.Model):
    SOURCE_EA = 'EA'
    SOURCE_FM = 'FM'
    SOURCE_CHOICES = [
        (SOURCE_EA, 'EA / SoFIFA / FIFAIndex'),
        (SOURCE_FM, 'FMInside'),
    ]

    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='source_ratings',
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
    )
    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )
    potential = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )
    source_url = models.URLField(blank=True)
    source_version = models.CharField(
        max_length=100,
        blank=True,
    )
    checked_at = models.DateField(
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            'player__last_name',
            'player__first_name',
            'source',
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'player',
                    'source',
                ],
                name='unique_player_source_rating',
            ),
        ]

    def __str__(self):
        return f'{self.player} - {self.get_source_display()} {self.rating}'


class PlayerFormSnapshot(models.Model):
    SOURCE_API_FOOTBALL = 'api_football'
    SOURCE_SPORTDB_FLASHSCORE = 'sportdb_flashscore'
    SOURCE_CHOICES = [
        (SOURCE_API_FOOTBALL, 'API-Football'),
        (SOURCE_SPORTDB_FLASHSCORE, 'SportDB / Flashscore'),
    ]

    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='form_snapshots',
    )
    source = models.CharField(
        max_length=40,
        choices=SOURCE_CHOICES,
        default=SOURCE_API_FOOTBALL,
    )
    fixture_id = models.CharField(max_length=80)
    fixture_date = models.DateField()
    league_api_football_id = models.PositiveIntegerField(null=True, blank=True)
    team_api_football_id = models.PositiveIntegerField(null=True, blank=True)
    team_name = models.CharField(max_length=120, blank=True)
    opponent_name = models.CharField(max_length=120, blank=True)
    minutes_played = models.PositiveSmallIntegerField(default=0)
    possible_minutes = models.PositiveSmallIntegerField(default=90)
    minutes_quote = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    started = models.BooleanField(default=False)
    substituted_in = models.BooleanField(default=False)
    captain = models.BooleanField(default=False)
    position = models.CharField(max_length=10, blank=True)
    rating = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
    )
    goals = models.PositiveSmallIntegerField(default=0)
    assists = models.PositiveSmallIntegerField(default=0)
    yellow_cards = models.PositiveSmallIntegerField(default=0)
    red_cards = models.PositiveSmallIntegerField(default=0)
    raw_payload = models.JSONField(default=dict, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            '-fixture_date',
            '-fixture_id',
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'player',
                    'source',
                    'fixture_id',
                ],
                name='unique_player_form_snapshot_source_fixture',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.possible_minutes:
            self.minutes_quote = strength_decimal(
                Decimal(self.minutes_played) /
                Decimal(self.possible_minutes) *
                Decimal('100')
            )
        else:
            self.minutes_quote = Decimal('0.00')

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f'{self.player} - {self.fixture_date} '
            f'{self.minutes_played} Min.'
        )


class PlayerStrengthProfile(models.Model):
    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name='strength_profile'
    )

    base_strength = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('50.00'),
    )
    form_modifier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    freshness = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
        help_text='Aktuelle Websoccer-Frische. Wirkt als Punktabzug, nicht als Multiplikator.',
    )
    final_strength = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('50.00'),
    )

    updated_at = models.DateTimeField(auto_now=True)

    def calculate_final_strength(self):
        self.final_strength = strength_decimal(
            self.base_strength +
            self.form_modifier
        )

        return self.final_strength

    def save(self, *args, **kwargs):
        self.calculate_final_strength()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.player} - "
            f"StÃ¤rke {self.final_strength:.2f}"
        )


class PlayerMarketValueSnapshot(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='market_value_snapshots',
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='market_value_snapshots',
    )
    recorded_at = models.DateField(default=timezone.localdate)
    value_eur = models.DecimalField(max_digits=15, decimal_places=2)
    profile_url = models.URLField(blank=True)
    source_version = models.CharField(max_length=100, blank=True)
    update_current = models.BooleanField(
        default=True,
        help_text='Aktualisiert Player.market_value und salary_per_match beim Speichern.',
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'source', 'recorded_at'],
                name='unique_player_market_value_snapshot',
            ),
        ]
        verbose_name = 'Marktwert-Snapshot'
        verbose_name_plural = 'Marktwert-Snapshots'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.update_current:
            salary_per_match = (
                self.value_eur / Decimal('1000000')
            ) * Decimal('5000')
            Player.objects.filter(pk=self.player_id).update(
                market_value=self.value_eur,
                salary_per_match=salary_per_match,
            )
        prune_snapshot_history(
            PlayerMarketValueSnapshot,
            {
                'player_id': self.player_id,
                'source_id': self.source_id,
            },
        )

    def __str__(self):
        return f'{self.player} - {self.value_eur:.0f} EUR'


class PlayerSeasonStat(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ws_season_stats',
    )
    season = models.CharField(max_length=20, default='2026/27')
    season_number = models.PositiveSmallIntegerField(default=1)
    competition = models.CharField(max_length=120, default='Liga')
    matches = models.PositiveSmallIntegerField(default=0)
    goals = models.PositiveSmallIntegerField(default=0)
    assists = models.PositiveSmallIntegerField(default=0)
    substitutions_in = models.PositiveSmallIntegerField(default=0)
    substitutions_out = models.PositiveSmallIntegerField(default=0)
    yellow_cards = models.PositiveSmallIntegerField(default=0)
    red_cards = models.PositiveSmallIntegerField(default=0)
    player_of_match_awards = models.PositiveSmallIntegerField(default=0)
    minutes_played = models.PositiveIntegerField(default=0)
    average_grade = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Websoccer-Note. 1.00 ist sehr gut, 6.00 schwach.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-season_number', 'competition']
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'season', 'competition'],
                name='unique_player_ws_season_stat',
            ),
        ]
        verbose_name = 'WS-Saisonstatistik'
        verbose_name_plural = 'WS-Saisonstatistiken'

    def __str__(self):
        return f'{self.player} - {self.season} {self.competition}'


class PlayerTransferHistory(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ws_transfer_history',
    )
    transfer_date = models.DateField(default=timezone.localdate)
    season = models.CharField(max_length=20, blank=True)
    from_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outgoing_ws_transfers',
    )
    to_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incoming_ws_transfers',
    )
    fee_eur = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transfer_date', '-id']
        verbose_name = 'WS-Transfer'
        verbose_name_plural = 'WS-Transfers'

    def __str__(self):
        return f'{self.player} - {self.transfer_date}'


class PlayerInjuryRecord(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ws_injury_records',
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    injury_type = models.CharField(max_length=120)
    days_missed = models.PositiveSmallIntegerField(default=0)
    competition = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date', '-id']
        verbose_name = 'WS-Verletzung'
        verbose_name_plural = 'WS-Verletzungen'

    def __str__(self):
        return f'{self.player} - {self.injury_type}'


class PlayerSuspensionRecord(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ws_suspension_records',
    )
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=120)
    matches_missed = models.PositiveSmallIntegerField(default=0)
    competition = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date', '-id']
        verbose_name = 'WS-Sperre'
        verbose_name_plural = 'WS-Sperren'

    def __str__(self):
        return f'{self.player} - {self.reason}'


class PlayerAwardTitle(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='ws_awards_titles',
    )
    title = models.CharField(max_length=120)
    season = models.CharField(max_length=20, blank=True)
    competition = models.CharField(max_length=120, blank=True)
    trophy_asset_id = models.CharField(
        max_length=80,
        blank=True,
        help_text='Dateiname oder ID aus Images/Trophies ohne Dateiendung.',
    )
    count = models.PositiveSmallIntegerField(default=1)
    awarded_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-awarded_at', '-id']
        verbose_name = 'WS-Auszeichnung/Titel'
        verbose_name_plural = 'WS-Auszeichnungen/Titel'

    COMPETITION_DEFAULT_ASSETS = {
        # Global — FIFA World Cup
        'FIFA World Cup':           'international cup 1',
        'World Cup':                'international cup 1',
        'Weltmeisterschaft':        'international cup 1',
        'WM':                       'international cup 1',
        # Global — secondary international tournaments
        'FIFA Confederations Cup':  'international cup 2',
        'Confederations Cup':       'international cup 2',
        'Konföderationen-Pokal':    'international cup 2',
        'Olympic Games':            'international cup 2',
        'Olympische Spiele':        'international cup 2',
        'Olympia':                  'international cup 2',
        'FIFA U-20 World Cup':      'international cup 2',
        'FIFA U-17 World Cup':      'international cup 2',
        # UEFA
        'UEFA European Championship': 'continental cup 1',
        'UEFA Euro':                'continental cup 1',
        'Europameisterschaft':      'continental cup 1',
        'EM':                       'continental cup 1',
        'UEFA Nations League':      'continental cup 2',
        'Nations League':           'continental cup 2',
        # CONMEBOL
        'Copa América':             'continental cup 1',
        'Copa America':             'continental cup 1',
        'CONMEBOL Copa América':    'continental cup 1',
        # CAF
        'Africa Cup of Nations':    'continental cup 1',
        'AFCON':                    'continental cup 1',
        'Afrikameisterschaft':      'continental cup 1',
        # AFC
        'AFC Asian Cup':            'continental cup 1',
        'Asian Cup':                'continental cup 1',
        'Asienmeisterschaft':       'continental cup 1',
        # CONCACAF
        'CONCACAF Gold Cup':        'continental cup 1',
        'Gold Cup':                 'continental cup 1',
        'CONCACAF Nations League':  'continental cup 2',
    }

    def save(self, *args, **kwargs):
        if not self.trophy_asset_id and self.title in self.COMPETITION_DEFAULT_ASSETS:
            self.trophy_asset_id = self.COMPETITION_DEFAULT_ASSETS[self.title]
        super().save(*args, **kwargs)

    @property
    def trophy_static_path(self):
        from .player_assets import get_cached_trophy_static_path

        return get_cached_trophy_static_path(self.trophy_asset_id)

    def __str__(self):
        return f'{self.player} - {self.title}'


class PlayerSourceRatingSnapshot(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='source_rating_snapshots',
    )
    source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='source_rating_snapshots',
    )
    recorded_at = models.DateField(default=timezone.localdate)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    potential = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    source_url = models.URLField(blank=True)
    source_version = models.CharField(max_length=100, blank=True)
    update_current = models.BooleanField(
        default=True,
        help_text='Aktualisiert PlayerSourceRating fuer die aktuelle Staerkeberechnung.',
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'source', 'recorded_at'],
                name='unique_player_source_rating_snapshot',
            ),
        ]
        verbose_name = 'Source-Rating-Snapshot'
        verbose_name_plural = 'Source-Rating-Snapshots'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.update_current and self.source.code in {
            PlayerSourceRating.SOURCE_EA,
            PlayerSourceRating.SOURCE_FM,
        }:
            PlayerSourceRating.objects.update_or_create(
                player=self.player,
                source=self.source.code,
                defaults={
                    'rating': self.rating,
                    'potential': self.potential,
                    'source_url': self.source_url,
                    'source_version': self.source_version,
                    'checked_at': self.recorded_at,
                    'notes': self.notes,
                },
            )
        prune_snapshot_history(
            PlayerSourceRatingSnapshot,
            {
                'player_id': self.player_id,
                'source_id': self.source_id,
            },
        )

    def __str__(self):
        return f'{self.player} - {self.source.code} {self.rating}'


class PlayerWeightedRatingSnapshot(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='weighted_rating_snapshots',
    )
    source = models.CharField(
        max_length=40,
        choices=PlayerFormSnapshot.SOURCE_CHOICES,
        default=PlayerFormSnapshot.SOURCE_SPORTDB_FLASHSCORE,
    )
    recorded_at = models.DateField(default=timezone.localdate)
    fixture_reference = models.CharField(max_length=120, blank=True)
    weighted_rating = models.DecimalField(max_digits=4, decimal_places=2)
    rating_minutes = models.PositiveSmallIntegerField(default=0)
    match_count = models.PositiveSmallIntegerField(default=0)
    window_label = models.CharField(
        max_length=80,
        default='Letzte 10 Spiele',
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'source', 'recorded_at', 'fixture_reference'],
                name='unique_player_weighted_rating_snapshot',
            ),
        ]
        verbose_name = 'Gewichteter Rating-Snapshot'
        verbose_name_plural = 'Gewichtete Rating-Snapshots'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        prune_snapshot_history(
            PlayerWeightedRatingSnapshot,
            {
                'player_id': self.player_id,
                'source': self.source,
            },
        )

    def __str__(self):
        return f'{self.player} - {self.weighted_rating:.2f}'


class PlayerStrengthSnapshot(models.Model):
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='strength_snapshots',
    )
    recorded_at = models.DateField(default=timezone.localdate)
    match_reference = models.CharField(max_length=120, blank=True)
    base_strength = models.DecimalField(max_digits=6, decimal_places=2)
    final_strength = models.DecimalField(max_digits=6, decimal_places=2)
    max_strength = models.DecimalField(max_digits=6, decimal_places=2)
    last_10_average_strength = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    freshness = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    form_modifier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'recorded_at', 'match_reference'],
                name='unique_player_strength_snapshot',
            ),
        ]
        verbose_name = 'Staerke-Snapshot'
        verbose_name_plural = 'Staerke-Snapshots'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        prune_snapshot_history(
            PlayerStrengthSnapshot,
            {
                'player_id': self.player_id,
            },
        )

    def __str__(self):
        return f'{self.player} - {self.recorded_at} {self.final_strength:.2f}'


class PlayerEditRequest(models.Model):
    FIELD_NATIONALITIES = 'nationalities'
    FIELD_REAL_LIFE_CLUB = 'real_life_club'
    FIELD_MARKET_VALUE = 'market_value'
    FIELD_MAIN_POSITIONS = 'main_positions'
    FIELD_SECONDARY_POSITIONS = 'secondary_positions'
    FIELD_SOURCE_RATING = 'source_rating'
    FIELD_DEFAULT_BASE = 'default_base'
    FIELD_CHOICES = [
        (FIELD_NATIONALITIES, 'Nationalitaet'),
        (FIELD_REAL_LIFE_CLUB, 'RL-Verein'),
        (FIELD_MARKET_VALUE, 'Marktwert'),
        (FIELD_MAIN_POSITIONS, 'Hauptpositionen'),
        (FIELD_SECONDARY_POSITIONS, 'Nebenpositionen'),
        (FIELD_SOURCE_RATING, 'Source Rating'),
        (FIELD_DEFAULT_BASE, 'Default-Basisstaerke'),
    ]

    STATUS_OPEN = 'open'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Offen'),
        (STATUS_ACCEPTED, 'Angenommen'),
        (STATUS_REJECTED, 'Abgelehnt'),
    ]

    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='edit_requests',
    )
    field_name = models.CharField(
        max_length=40,
        choices=FIELD_CHOICES,
    )
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    requester_name = models.CharField(max_length=120, blank=True)
    requester_note = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    decision_note = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decided_player_edit_requests',
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            'status',
            '-created_at',
        ]
        verbose_name = 'Spielerbearbeitungsantrag'
        verbose_name_plural = 'Spielerbearbeitungsantraege'

    def __str__(self):
        return f'{self.player} - {self.get_field_name_display()}'

    def _parse_decimal(self, value):
        normalized = value.strip().replace('.', '').replace(',', '.')
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise ValidationError('Der neue Marktwert ist keine gueltige Zahl.') from exc

    def _parse_positions(self, value):
        valid_positions = {position for position, label in Player.POSITION_CHOICES}
        positions = [
            position.strip().upper()
            for position in value.replace(';', ',').split(',')
            if position.strip()
        ]

        if len(positions) > 3:
            raise ValidationError('Es sind maximal drei Positionen erlaubt.')

        invalid_positions = [
            position
            for position in positions
            if position not in valid_positions
        ]
        if invalid_positions:
            raise ValidationError(
                f"Ungueltige Position(en): {', '.join(invalid_positions)}"
            )

        return positions

    def apply_to_player(self):
        player = self.player
        value = self.new_value.strip()

        if self.field_name == self.FIELD_NATIONALITIES:
            player.nationalities = value
            player.save(update_fields=['nationalities'])
            return

        if self.field_name == self.FIELD_REAL_LIFE_CLUB:
            if not value:
                player.real_life_club = None
            else:
                club = None
                if value.isdigit():
                    club = Club.objects.filter(pk=int(value)).first()

                if club is None:
                    club = Club.objects.filter(name__iexact=value).first()

                if club is None:
                    raise ValidationError('Der neue RL-Verein wurde nicht gefunden.')

                player.real_life_club = club

            player.save(update_fields=['real_life_club'])
            return

        if self.field_name == self.FIELD_MARKET_VALUE:
            player.market_value = self._parse_decimal(value)
            player.save(update_fields=['market_value'])
            return

        if self.field_name == self.FIELD_MAIN_POSITIONS:
            positions = self._parse_positions(value)
            player.main_position_1 = positions[0] if len(positions) > 0 else ''
            player.main_position_2 = positions[1] if len(positions) > 1 else ''
            player.main_position_3 = positions[2] if len(positions) > 2 else ''
            player.position = player.main_position_1
            player.save(
                update_fields=[
                    'main_position_1',
                    'main_position_2',
                    'main_position_3',
                    'position',
                ]
            )
            return

        if self.field_name == self.FIELD_SECONDARY_POSITIONS:
            positions = self._parse_positions(value)
            player.secondary_position_1 = positions[0] if len(positions) > 0 else ''
            player.secondary_position_2 = positions[1] if len(positions) > 1 else ''
            player.secondary_position_3 = positions[2] if len(positions) > 2 else ''
            player.primary_position = player.secondary_position_1
            player.source_positions = player.secondary_position_1
            player.save(
                update_fields=[
                    'secondary_position_1',
                    'secondary_position_2',
                    'secondary_position_3',
                    'primary_position',
                    'source_positions',
                ]
            )
            return

        raise ValidationError(
            'Dieser Antrag ist eine Markierung und muss manuell bearbeitet werden.'
        )

    def accept(self, user=None):
        self.apply_to_player()
        self.status = self.STATUS_ACCEPTED
        self.decided_by = user if user and user.is_authenticated else None
        self.decided_at = timezone.now()
        self.save(update_fields=['status', 'decided_by', 'decided_at', 'updated_at'])

    def reject(self, user=None):
        self.status = self.STATUS_REJECTED
        self.decided_by = user if user and user.is_authenticated else None
        self.decided_at = timezone.now()
        self.save(update_fields=['status', 'decided_by', 'decided_at', 'updated_at'])


class PlayerDataReview(Player):
    class Meta:
        proxy = True
        verbose_name = 'Spieler-Datenpruefung'
        verbose_name_plural = 'Spieler-Datenpruefung'


class ManagerProfile(models.Model):
    TRAINER_TYPE_CHOICES = [
        ('laptoptrainer', 'Laptoptrainer'),
        ('taktikfuchs', 'Taktikfuchs'),
        ('motivator', 'Motivator'),
        ('talentschmied', 'Talentschmied'),
        ('transferstratege', 'Transferstratege'),
        ('pokaljager', 'Pokaljäger'),
        ('offensivarchitekt', 'Offensivarchitekt'),
        ('underdog', 'Underdog-Flüsterer'),
        ('aufstiegsheld', 'Aufstiegsheld'),
        ('defensivmeister', 'Defensivmeister'),
        ('weltenbummler', 'Weltenbummler'),
        ('serienmeister', 'Serienmeister'),
        ('feuerwehrmann', 'Feuerwehrmann'),
        ('vereinslegende', 'Vereinslegende'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='manager_profile',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100, unique=True)
    trainer_type = models.CharField(
        max_length=30,
        choices=TRAINER_TYPE_CHOICES,
        default='laptoptrainer',
    )
    nationality_flag = models.CharField(
        max_length=200,
        blank=True,
        default='',
    )
    nationality_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
    )
    member_since = models.DateField(null=True, blank=True)
    profile_image = models.CharField(max_length=200, blank=True, default='')
    name_confirmed = models.BooleanField(
        default=False,
        help_text='True, sobald der Manager einen eigenen Namen gespeichert hat (nicht mehr der Standard-Username).',
    )
    xp = models.PositiveIntegerField(default=0)
    xp_max = models.PositiveIntegerField(default=15000)
    level = models.PositiveIntegerField(default=1)
    highscore = models.CharField(max_length=50, blank=True, default='–')
    updated_at = models.DateTimeField(auto_now=True)
    favourite_club = models.ForeignKey(
        'Club',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Lieblingsverein',
    )

    class Meta:
        verbose_name = 'Manager-Profil'
        verbose_name_plural = 'Manager-Profile'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(nationality_name='') | ~models.Q(nationality_flag=''),
                name='managerprofile_nationality_name_requires_flag',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.nationality_name and not self.nationality_flag:
            raise ValidationError(
                {'nationality_name': 'Eine Nationalität darf nur gesetzt werden, wenn auch ein Flag-URL vorhanden ist.'}
            )

    @property
    def trainer_type_label(self):
        return dict(self.TRAINER_TYPE_CHOICES).get(self.trainer_type, self.trainer_type)

    @property
    def xp_pct(self):
        if not self.xp_max:
            return 0
        return round(self.xp / self.xp_max * 100)

    @property
    def xp_label(self):
        return f'{self.xp:,} / {self.xp_max:,} XP'.replace(',', '.')


class ManagerCareerStation(models.Model):
    manager = models.ForeignKey(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='career_stations',
    )
    club = models.ForeignKey(
        'Club',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manager_career_stations',
    )
    order = models.PositiveSmallIntegerField(default=1)
    custom_club_name = models.CharField(max_length=150, blank=True)
    city_name = models.CharField(max_length=120)
    city_country = models.CharField(max_length=100, blank=True)
    map_x = models.PositiveSmallIntegerField(default=271)
    map_y = models.PositiveSmallIntegerField(default=214)
    started_at = models.DateField(null=True, blank=True)
    ended_at = models.DateField(null=True, blank=True)
    games_played = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['manager', 'order']
        verbose_name = 'Manager-Karriere-Station'
        verbose_name_plural = 'Manager-Karriere-Stationen'

    def __str__(self):
        return f'{self.manager} – {self.city_name}'

    @property
    def is_current(self):
        return self.ended_at is None

    @property
    def period_label(self):
        if self.started_at:
            start = self.started_at.strftime('%-d. %b %Y')
        else:
            start = '?'
        if self.ended_at:
            end = self.ended_at.strftime('%-d. %b %Y')
        else:
            end = 'heute'
        return f'{start} – {end}'

    @property
    def titles_count(self):
        if self.club_id:
            from django.db.models import Sum
            result = ClubTrophy.objects.filter(club_id=self.club_id).aggregate(total=Sum('count'))
            return result['total'] or 0
        return 0


# ============================================================
#  Präsident — Saisonziele & Hoeneß-Coin
# ============================================================

class SeasonGoal(models.Model):
    """Vom Präsidenten zu Saisonbeginn verkündetes Ziel eines Vereins.

    Das Ziel wird aus der Kaderstärke (Summe der Top-11 base_strength)
    relativ zur restlichen Liga abgeleitet und zu Saisonende gegen die
    erreichte Platzierung geprüft.
    """

    TIER_MEISTER = 'meister'
    TIER_TOP4 = 'top4'
    TIER_INTERNATIONAL = 'international'
    TIER_MITTELFELD = 'mittelfeld'
    TIER_KLASSENERHALT = 'klassenerhalt'
    TIER_CHOICES = [
        (TIER_MEISTER, 'Meister'),
        (TIER_TOP4, 'Top 4'),
        (TIER_INTERNATIONAL, 'Internationale Plätze'),
        (TIER_MITTELFELD, 'Gesichertes Mittelfeld'),
        (TIER_KLASSENERHALT, 'Klassenerhalt'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='season_goals',
    )
    season_number = models.PositiveSmallIntegerField(default=1)
    goal_tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    rank_in_league = models.PositiveSmallIntegerField(
        help_text='Kaderstärke-Rang innerhalb der Liga bei Zielverkündung.',
    )
    league_size = models.PositiveSmallIntegerField(default=0)
    squad_strength = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Summe der Top-11 base_strength bei Zielverkündung.',
    )
    required_max_rank = models.PositiveSmallIntegerField(
        default=0,
        help_text='Maximal erlaubter Endplatz, um das Ziel zu erfüllen.',
    )
    final_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    achieved = models.BooleanField(
        null=True,
        blank=True,
        help_text='Leer = noch nicht ausgewertet, sonst erfüllt/verfehlt.',
    )
    declared_at = models.DateTimeField(auto_now_add=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Saisonziel'
        verbose_name_plural = 'Saisonziele'
        ordering = ['-season_number', 'rank_in_league']
        constraints = [
            models.UniqueConstraint(
                fields=['club', 'season_number'],
                name='seasongoal_unique_club_season',
            ),
        ]

    def __str__(self):
        return f'{self.club} – Saison {self.season_number}: {self.goal_tier_label}'

    @property
    def goal_tier_label(self):
        return dict(self.TIER_CHOICES).get(self.goal_tier, self.goal_tier)

    @property
    def is_pending(self):
        return self.achieved is None


class HoenessCoin(models.Model):
    """Hoeneß-Coin-Guthaben eines Managers — Belohnung für erfüllte Saisonziele."""

    manager = models.OneToOneField(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='hoeness_coins',
    )
    amount = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Hoeneß-Coin-Guthaben'
        verbose_name_plural = 'Hoeneß-Coin-Guthaben'

    def __str__(self):
        return f'{self.manager} – {self.amount} Hoeneß-Coin'


class CoinTransaction(models.Model):
    """Protokolliert jede einzelne Hoeneß-Coin-Buchung (Einnahme oder Ausgabe)."""

    REASON_WIN = 'win'
    REASON_BIG_WIN = 'big_win'
    REASON_SEASON_GOAL = 'season_goal'
    REASON_BOOST_TRANSFER = 'boost_transfer'
    REASON_SCOUT_TALENT = 'scout_talent'

    REASON_CHOICES = [
        (REASON_WIN,            'Sieg'),
        (REASON_BIG_WIN,        'Kantersieg'),
        (REASON_SEASON_GOAL,    'Saisonziel erfüllt'),
        (REASON_BOOST_TRANSFER, 'Transfermarkt-Boost'),
        (REASON_SCOUT_TALENT,   'Talentscout'),
    ]

    manager = models.ForeignKey(
        ManagerProfile,
        on_delete=models.CASCADE,
        related_name='coin_transactions',
    )
    amount = models.SmallIntegerField(
        help_text='Positiv = verdient, negativ = ausgegeben.',
    )
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Coin-Transaktion'
        verbose_name_plural = 'Coin-Transaktionen'
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f'{self.manager} {sign}{self.amount} ({self.get_reason_display()})'


class GameSeasonState(models.Model):
    """Globaler, vom Admin gesteuerter Saison-Status.

    Hält die aktuelle Saisonnummer (beginnt bei 0) und ob die Saison
    offiziell gestartet wurde. Erst nach dem Start verkündet der
    Präsident die Saisonziele — vorher bleiben sie unter Verschluss.
    Es existiert nur eine Zeile (Singleton).
    """

    current_season = models.PositiveSmallIntegerField(
        default=0,
        help_text='Aktuelle Saisonnummer (beginnt bei 0).',
    )
    is_started = models.BooleanField(
        default=False,
        help_text='Erst wenn aktiv, verkündet der Präsident die Saisonziele.',
    )
    started_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Saison-Status'
        verbose_name_plural = 'Saison-Status'

    def __str__(self):
        zustand = 'gestartet' if self.is_started else 'nicht gestartet'
        return f'Saison {self.current_season} ({zustand})'


class PresidentSatisfaction(models.Model):
    """Präsident-Zufriedenheit — vereinsgebunden, pro Manager-Club-Kombination.

    Startet bei 100, wenn ein Manager einen Verein übernimmt (frischer Start).
    Sinkt um 50 bei verfehlem Saisonziel, steigt um 50 bei Zielerreichung.
    Wird beim Vereinswechsel NICHT übertragen — neuer Verein = Neustart bei 100.
    Bei 0 % erscheint der Manager in der Admin-Übersicht "Entlassungskandidaten".
    """

    manager = models.ForeignKey(
        'ManagerProfile',
        on_delete=models.CASCADE,
        related_name='president_satisfactions',
        verbose_name='Manager',
    )
    club = models.ForeignKey(
        'Club',
        on_delete=models.CASCADE,
        related_name='president_satisfactions',
        verbose_name='Verein',
    )
    value = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Zufriedenheit (0–100)',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('manager', 'club')]
        ordering = ['value', '-updated_at']
        verbose_name = 'Präsident-Zufriedenheit'
        verbose_name_plural = 'Präsident-Zufriedenheiten'

    def __str__(self):
        return f'{self.manager} @ {self.club} — {self.value} %'


class ManagerAtRisk(PresidentSatisfaction):
    """Proxy-Modell: zeigt nur Manager mit Zufriedenheit 0 % (Entlassungskandidaten)."""

    class Meta:
        proxy = True
        verbose_name = 'Entlassungskandidat'
        verbose_name_plural = 'Entlassungskandidaten (Zufriedenheit 0 %)'


# ── Sportgericht ───────────────────────────────────────────────────────────────

class InactivityRecord(models.Model):
    """Protokolliert jeden Spieltag, an dem ein Manager kein Team aufgestellt hat."""

    SQUAD_PRO_LABEL = 'pro'
    SQUAD_U21_LABEL = 'u21'
    SCOPE_CHOICES = [
        ('pro', 'Profis'),
        ('u21', 'U21'),
    ]

    manager = models.ForeignKey(
        'ManagerProfile',
        on_delete=models.CASCADE,
        related_name='inactivity_records',
        verbose_name='Manager',
    )
    club = models.ForeignKey(
        'Club',
        on_delete=models.SET_NULL,
        null=True,
        related_name='inactivity_records',
        verbose_name='Verein',
    )
    squad_scope = models.CharField(
        max_length=10,
        choices=SCOPE_CHOICES,
        default='pro',
        verbose_name='Mannschaft',
    )
    season = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Saison',
    )
    matchday_label = models.CharField(
        max_length=80,
        blank=True,
        verbose_name='Spieltag',
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Erfasst am',
    )

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = 'Inaktivitäts-Eintrag'
        verbose_name_plural = 'Inaktivitäts-Einträge'

    def __str__(self):
        return f'{self.manager} | {self.get_squad_scope_display()} | {self.matchday_label} ({self.season})'


class InactivityPenalty(models.Model):
    """Strafpunkt für Manager, die bereits einmal wegen Inaktivität entlassen wurden.

    Senkt die Toleranzschwelle: 3→2 hintereinander, 5→4 pro Saison.
    """

    manager = models.ForeignKey(
        'ManagerProfile',
        on_delete=models.CASCADE,
        related_name='inactivity_penalties',
        verbose_name='Manager',
    )
    given_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Erteilt am',
    )
    reason = models.TextField(
        blank=True,
        verbose_name='Begründung',
    )

    class Meta:
        ordering = ['-given_at']
        verbose_name = 'Inaktivitäts-Strafpunkt'
        verbose_name_plural = 'Inaktivitäts-Strafpunkte'

    def __str__(self):
        return f'Strafpunkt: {self.manager} ({self.given_at:%d.%m.%Y})'


class SupportTicket(models.Model):
    """Support-Ticket, das ein Manager einreichen kann."""

    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        ('open', 'Offen'),
        ('in_progress', 'In Bearbeitung'),
        ('closed', 'Abgeschlossen'),
    ]

    manager = models.ForeignKey(
        'ManagerProfile',
        on_delete=models.CASCADE,
        related_name='support_tickets',
        verbose_name='Manager',
    )
    title = models.CharField(
        max_length=200,
        verbose_name='Titel',
    )
    description = models.TextField(
        verbose_name='Beschreibung',
    )
    screenshot = models.FileField(
        upload_to='support_tickets/',
        blank=True,
        null=True,
        verbose_name='Screenshot',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name='Status',
    )
    admin_response = models.TextField(
        blank=True,
        verbose_name='Admin-Antwort',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Erstellt am',
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Abgeschlossen am',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Support-Ticket'
        verbose_name_plural = 'Support-Tickets'

    def __str__(self):
        return f'#{self.pk} {self.title} ({self.get_status_display()}) — {self.manager}'


class ClubFinancialTransaction(models.Model):
    CATEGORY_CHOICES = [
        ('ticketverkauf',    'Ticketverkauf'),
        ('sponsor',          'Sponsoren'),
        ('tv_gelder',        'TV-Gelder'),
        ('transfer_einnahme','Transfer (Einnahme)'),
        ('leih_einnahme',    'Leiheinnahme'),
        ('praemie',          'Prämie'),
        ('sonstige_einnahme','Sonstige Einnahme'),
        ('transfer_ausgabe', 'Transfer (Ausgabe)'),
        ('profigehalt',      'Profigehalt'),
        ('jugendgehalt',     'Jugendgehalt'),
        ('stadionkosten',    'Stadionkosten'),
        ('stadionumfeld',    'Stadionumfeld'),
        ('sonstige_ausgabe', 'Sonstige Ausgabe'),
    ]

    INCOME_CATEGORIES = {
        'ticketverkauf', 'sponsor', 'tv_gelder',
        'transfer_einnahme', 'leih_einnahme', 'praemie', 'sonstige_einnahme',
    }

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='financial_transactions',
        verbose_name='Verein',
    )
    date = models.DateField(
        default=timezone.localdate,
        verbose_name='Datum',
    )
    season = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Saison',
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        verbose_name='Kategorie',
    )
    description = models.CharField(
        max_length=200,
        verbose_name='Verwendungszweck',
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Betrag (€)',
        help_text='Positiv = Einnahme, Negativ = Ausgabe.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Finanztransaktion'
        verbose_name_plural = 'Finanztransaktionen'

    @property
    def is_income(self):
        return self.amount >= 0

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f'{self.club} | {self.get_category_display()} | {sign}{self.amount:,.0f} € ({self.date})'


class ClubSponsor(models.Model):
    TYPE_CHOICES = [
        ('tv',       'TV-Vertrag'),
        ('trikot',   'Trikotsponsor'),
        ('haupt',    'Hauptsponsor'),
        ('ausrüster','Ausrüster'),
        ('sonstig',  'Sonstige Sponsoren'),
    ]

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name='sponsors',
        verbose_name='Verein',
    )
    name = models.CharField(max_length=100, verbose_name='Sponsorname')
    sponsor_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name='Typ',
    )
    amount_per_season = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Betrag / Saison (€)',
    )
    season = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Saison',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktiv')

    class Meta:
        ordering = ['sponsor_type', 'name']
        verbose_name = 'Vereinssponsor'
        verbose_name_plural = 'Vereinssponsoren'

    def __str__(self):
        return f'{self.club} — {self.get_sponsor_type_display()}: {self.name} ({self.amount_per_season:,.0f} €/Saison)'
