"""Sichtbarer Microsoft Edge über Playwright mit persistentem Profil.

Ein persistenter Kontext (``launch_persistent_context``) behält Cookies und
Anmeldungen über Läufe hinweg, sodass Login-/Cookie-Banner nur einmal manuell
bestätigt werden müssen. Der Browser läuft standardmäßig sichtbar
(``headless=False``).
"""

from playwright.sync_api import sync_playwright


class Browser:
    """Kontextmanager um einen persistenten Edge-Kontext."""

    def __init__(self, config, logger):
        self.config = config
        self.log = logger
        self._pw = None
        self.context = None
        self.page = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.log.info('Starte Microsoft Edge (Kanal=%s, sichtbar=%s) ...',
                      self.config.browser_channel, not self.config.headless)
        self.context = self._pw.chromium.launch_persistent_context(
            user_data_dir=self.config.user_data_dir,
            channel=self.config.browser_channel,
            headless=self.config.headless,
            viewport={'width': 1440, 'height': 900},
            locale='de-DE',
        )
        self.context.set_default_timeout(30_000)
        self.page = (self.context.pages[0]
                     if self.context.pages else self.context.new_page())
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.context is not None:
                self.context.close()
        finally:
            if self._pw is not None:
                self._pw.stop()
        return False
