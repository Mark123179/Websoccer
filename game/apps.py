from django.apps import AppConfig


class GameConfig(AppConfig):
    name = 'game'

    def ready(self):
        import game.signals  # noqa: F401 — connects signal receivers
        import game.club_import.league_guard  # noqa: F401
