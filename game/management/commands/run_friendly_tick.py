from django.core.management.base import BaseCommand
from game.friendlies.services import run_tick


class Command(BaseCommand):
    help = 'Verfällt offene Freundschaftsspiel-Anfragen und simuliert fällige Partien.'

    def handle(self, *args, **options):
        result = run_tick()
        self.stdout.write(self.style.SUCCESS(
            f"Freundschaftsspiele: {result['expired']} verfallen, "
            f"{result['processed']} fällige Partien verarbeitet."
        ))