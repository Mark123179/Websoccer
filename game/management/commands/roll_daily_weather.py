"""Nächtlicher Wetter-Tick: würfelt fehlende Sim-Tage bis heute + 7.

Idempotent: bereits gewürfeltes Wetter ist unveränderlich und wird nie
überschrieben. Der reguläre Nachtlauf würfelt effektiv nur "heute + 7";
nach Erst-Deploy oder verpassten Ticks werden alle fehlenden Tage im
Fenster nachgefüllt.
"""

from django.core.management.base import BaseCommand

from game.weather_service import ensure_weather_window


class Command(BaseCommand):
    help = 'Würfelt globales Tageswetter für heute bis heute + 7 (idempotent).'

    def handle(self, *args, **options):
        created = ensure_weather_window()
        if created:
            self.stdout.write(self.style.SUCCESS(
                f'Wetter gewürfelt: {created} neue Sim-Tage.'
            ))
        else:
            self.stdout.write('Wetter vollständig — nichts zu würfeln.')
