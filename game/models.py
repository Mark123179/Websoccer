from django.db import models


class League(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Club(models.Model):
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
    age = models.IntegerField()

    position = models.CharField(
        max_length=10,
        choices=POSITION_CHOICES
    )

    potential = models.IntegerField(default=50)

    market_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


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