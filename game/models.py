from django.db import models


COUNTRY_FLAGS = {
    'Algerien': '🇩🇿',
    'Belgien': '🇧🇪',
    'Brasilien': '🇧🇷',
    'Deutschland': '🇩🇪',
    'Elfenbeinküste': '🇨🇮',
    'England': '🏴',
    'Frankreich': '🇫🇷',
    'Gambia': '🇬🇲',
    'Guinea': '🇬🇳',
    'Guinea-Bissau': '🇬🇼',
    'Irland': '🇮🇪',
    'Island': '🇮🇸',
    'Italien': '🇮🇹',
    'Japan': '🇯🇵',
    'Kanada': '🇨🇦',
    'Kolumbien': '🇨🇴',
    'Kosovo': '🇽🇰',
    'Kroatien': '🇭🇷',
    'Liberia': '🇱🇷',
    'Libyen': '🇱🇾',
    'Nigeria': '🇳🇬',
    'Norwegen': '🇳🇴',
    'Österreich': '🇦🇹',
    'Polen': '🇵🇱',
    'Portugal': '🇵🇹',
    'Schweden': '🇸🇪',
    'Schweiz': '🇨🇭',
    'Senegal': '🇸🇳',
    'Serbien': '🇷🇸',
    'Südkorea': '🇰🇷',
    'Türkei': '🇹🇷',
    'Vereinigte Staaten': '🇺🇸',
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

        return f'game/images/crests/{self.fm_inside_id}.png'


class Player(models.Model):
    POSITION_CHOICES = [
        ('TW', 'Torwart'),
        ('IV', 'Innenverteidiger'),
        ('LV', 'Linksverteidiger'),
        ('RV', 'Rechtsverteidiger'),
        ('ZDM', 'Zentrales Defensives Mittelfeld'),
        ('ZM', 'Zentrales Mittelfeld'),
        ('ZOM', 'Zentrales Offensives Mittelfeld'),
        ('LF', 'Linker Flügel'),
        ('RF', 'Rechter Flügel'),
        ('ST', 'Stürmer'),
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
                'flag': COUNTRY_FLAGS.get(country, '🏳'),
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
            f"Stärke {self.final_strength}"
        )
