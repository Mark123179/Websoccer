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
    budget = models.DecimalField(max_digits=12, decimal_places=2)
    league = models.ForeignKey(League, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Player(models.Model):
    POSITION_CHOICES = [
        ('GK', 'Torwart'),
        ('DEF', 'Verteidiger'),
        ('MID', 'Mittelfeld'),
        ('ATT', 'Stürmer'),
    ]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    age = models.IntegerField()
    strength = models.IntegerField()
    potential = models.IntegerField()

    position = models.CharField(
        max_length=3,
        choices=POSITION_CHOICES
    )

    club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    market_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"