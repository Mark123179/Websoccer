from django.contrib.staticfiles import finders
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


COUNTRY_FLAG_ASSETS = {
    'Algerien': {'asset_id': '5', 'code': 'DZ'},
    'Brasilien': {'asset_id': '1651', 'code': 'BR'},
    'Deutschland': {'asset_id': '771', 'code': 'DE'},
    'Elfenbeink\u00fcste': {'asset_id': '24', 'code': 'CI'},
    'England': {'asset_id': '765', 'code': 'ENG'},
    'Frankreich': {'asset_id': '769', 'code': 'FR'},
    'Gambia': {'asset_id': '20', 'code': 'GM'},
    'Guinea': {'asset_id': '22', 'code': 'GN'},
    'Guinea-Bissau': {'asset_id': '23', 'code': 'GW'},
    'Irland': {'asset_id': '789', 'code': 'IE'},
    'Italien': {'asset_id': '776', 'code': 'IT'},
    'Japan': {'asset_id': '116', 'code': 'JP'},
    'Kanada': {'asset_id': '364', 'code': 'CA'},
    'Kolumbien': {'asset_id': '1653', 'code': 'CO'},
    'Kroatien': {'asset_id': '761', 'code': 'HR'},
    'Liberia': {'asset_id': '27', 'code': 'LR'},
    'Libyen': {'asset_id': '28', 'code': 'LY'},
    'Nigeria': {'asset_id': '38', 'code': 'NG'},
    'Norwegen': {'asset_id': '786', 'code': 'NO'},
    '\u00d6sterreich': {'asset_id': '755', 'code': 'AT'},
    'Portugal': {'asset_id': '788', 'code': 'PT'},
    'Schweden': {'asset_id': '797', 'code': 'SE'},
    'Schweiz': {'asset_id': '798', 'code': 'CH'},
    'Senegal': {'asset_id': '41', 'code': 'SN'},
    'Serbien': {'asset_id': '802', 'code': 'RS'},
    'S\u00fcdkorea': {'asset_id': '135', 'code': 'KR'},
    'T\u00fcrkei': {'asset_id': '799', 'code': 'TR'},
    'Vereinigte Staaten': {'asset_id': '390', 'code': 'US'},
}

class League(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Club(models.Model):
    fm_inside_id = models.PositiveBigIntegerField(
        unique=True,
        null=True,
        blank=True
    )

    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20)
    founded_year = models.IntegerField()

    budget = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE
    )

    def __str__(self):
        return self.name

    @property
    def crest_static_path(self):
        if not self.fm_inside_id:
            return ''

        return f'game/images/crests/{self.fm_inside_id}.svg'

    @property
    def kit_static_paths(self):
        if not self.fm_inside_id:
            return []

        return [
            {
                'label': 'Heim',
                'path': f'game/images/kits/{self.fm_inside_id}_home.svg',
            },
            {
                'label': 'Auswärts',
                'path': f'game/images/kits/{self.fm_inside_id}_away.svg',
            },
            {
                'label': 'Third',
                'path': f'game/images/kits/{self.fm_inside_id}_third.svg',
            },
        ]


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
    age = models.IntegerField()

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

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def portrait_static_path(self):
        if not self.fm_inside_id:
            return 'game/images/default_player.svg'

        path = f'game/images/players/{self.fm_inside_id}.svg'
        if finders.find(path):
            return path

        return 'game/images/default_player.svg'

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
                'flag_static_path': (
                    f'game/images/flags/'
                    f"{COUNTRY_FLAG_ASSETS[country]['asset_id']}.svg"
                ) if country in COUNTRY_FLAG_ASSETS else '',
            }
            for country in countries
        ]

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
    def calculated_base_strength(self):
        ea_rating = self.ea_source_rating
        fm_rating = self.fm_source_rating

        if not ea_rating or not fm_rating:
            return None

        return ea_rating.rating + fm_rating.rating

    @property
    def calculated_potential_strength(self):
        ea_rating = self.ea_source_rating
        fm_rating = self.fm_source_rating

        if (
            not ea_rating
            or not fm_rating
            or ea_rating.potential is None
            or fm_rating.potential is None
        ):
            return None

        return ea_rating.potential + fm_rating.potential

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
            lines.append(
                f'Base = EA + FM = {self.calculated_base_strength}'
            )
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
                'Potential-Ceiling = EA Potential + FM Potential = '
                f'{self.calculated_potential_strength}'
            )

        return ' | '.join(lines)


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


class PlayerStrengthProfile(models.Model):
    player = models.OneToOneField(
        Player,
        on_delete=models.CASCADE,
        related_name='strength_profile'
    )

    base_strength = models.IntegerField(default=50)
    form_modifier = models.IntegerField(default=0)
    final_strength = models.IntegerField(default=50)

    updated_at = models.DateTimeField(auto_now=True)

    def calculate_final_strength(self):
        self.final_strength = (
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
            f"StÃ¤rke {self.final_strength}"
        )


