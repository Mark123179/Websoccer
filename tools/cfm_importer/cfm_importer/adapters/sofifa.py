"""SoFIFA-Adapter — Match über Name + Geburtsdatum, Rohwerte.

Selektoren gekapselt. Matching wie bei FMInside über normalisierten Namen +
Geburtsdatum (Nationalität als Tie-Breaker). Fehlendes SoFIFA blockiert den
Import NICHT (kein Eintrag wird übertragen). Getrennte Rohwerte für Feldspieler
und Torhüter werden über die Attributnamen abgebildet.
"""

import re

from .. import normalize
from .base import (
    PageError,
    attr_or_empty,
    detect_block,
    first_int,
    text_or_empty,
)

BASE = 'https://sofifa.com'


class SoFIFAAdapter:
    def __init__(self, page, config, logger):
        self.page = page
        self.config = config
        self.log = logger

    def _goto(self, url):
        self.page.goto(url, wait_until='domcontentloaded')
        self.page.wait_for_timeout(int(self.config.pause('page_load_ms', 1500) * 1000))
        detect_block(self.page)

    def lookup(self, *, display_name, date_of_birth, nationality, warnings):
        target_name = normalize.normalize_name(display_name)
        target_dob = normalize.normalize_dob(date_of_birth)
        if not target_name:
            warnings.append('SoFIFA: kein Name für die Suche vorhanden.')
            return None

        try:
            self._goto(f'{BASE}/players?keyword={display_name.replace(" ", "+")}')
        except PageError:
            warnings.append('SoFIFA: Suchseite nicht erreichbar.')
            return None

        candidates = self._search_results()
        match = self._pick(candidates, target_name, warnings)
        if not match:
            # SoFIFA ist optional — nur Hinweis, kein Fehler.
            warnings.append('SoFIFA: kein eindeutiger Treffer (optional).')
            return None

        try:
            self._goto(match['url'])
            return self._scrape_player(match)
        except PageError as exc:
            warnings.append(f'SoFIFA: Spielerseite nicht lesbar ({exc}).')
            return None

    # ── Selektoren ──────────────────────────────────────────────────────────
    def _search_results(self):
        links = self.page.locator('a[href*="/player/"]')
        out = []
        try:
            for i in range(min(links.count(), 25)):
                href = attr_or_empty(links.nth(i), 'href')
                name = text_or_empty(links.nth(i))
                pid = self._player_id(href)
                if pid and name:
                    out.append({
                        'id': pid, 'name': name,
                        'url': href if href.startswith('http') else f'{BASE}{href}'})
        except Exception:
            pass
        return out

    @staticmethod
    def _player_id(href):
        m = re.search(r'/player/(\d+)', href or '')
        return m.group(1) if m else None

    def _pick(self, candidates, target_name, warnings):
        hits = [c for c in candidates
                if normalize.normalize_name(c['name']) == target_name]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            warnings.append(f'SoFIFA: {len(hits)} Namenstreffer — uneindeutig.')
        return None

    def _scrape_player(self, match):
        rating = first_int(text_or_empty(
            self.page.locator('.player-overall, [data-overall]')))
        potential = first_int(text_or_empty(
            self.page.locator('.player-potential, [data-potential]')))
        attrs = self._attributes()
        return {
            'id': match['id'],
            'url': match['url'],
            'rating': rating,
            'potential': potential,
            'attrs': attrs,
        }

    def _attributes(self):
        """Liest Einzelattribute als {Label: Wert}. Leer, wenn nicht gefunden."""
        attrs = {}
        items = self.page.locator('li:has(.bp3-tag), .grid li')
        try:
            for i in range(min(items.count(), 120)):
                raw = text_or_empty(items.nth(i))
                m = re.match(r'\s*(\d{1,3})\s+([A-Za-zÀ-ÿ /]+)', raw)
                if m:
                    value, label = m.group(1), m.group(2).strip().lower()
                    attrs[label] = int(value)
        except Exception:
            pass
        return attrs
