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


class Player(models.Model):
    POSITION_CHOICES = [
        ('TW', 'Torwart'),
        ('IV', 'Innenverteidiger'),
        ('LV', 'Linksverteidiger'),
        ('RV', 'Rechtsverteidiger'),
        ('ZDM', 'Zentrales Defensives Mittelfeld'),
        ('ZM', 'Zentrales Mittelfeld'),
        ('ZOM', 'Zentrales Offensives Mittelfeld'),
        ('LF', 'Linker FlÃ¼gel'),
        ('RF', 'Rechter FlÃ¼gel'),
        ('ST', 'StÃ¼rmer'),
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
        choices=POSITION_CHOICES
    )
    primary_position = models.CharField(
        max_length=100,
        blank=True
    )
    source_positions = models.CharField(
        max_length=100,
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

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

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

