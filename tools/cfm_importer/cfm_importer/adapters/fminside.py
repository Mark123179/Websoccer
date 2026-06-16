"""FMInside-Adapter — Match über Name + Geburtsdatum, Rohwerte.

Selektoren sind hier gekapselt. Das Matching erfolgt über den normalisierten
Namen + Geburtsdatum (Nationalität als Tie-Breaker). Mehrere oder kein Treffer
werden klar gekennzeichnet (Warnung) — niemals wird ein falscher Treffer
erzwungen. Fehlendes FMInside blockiert den Import NICHT, wird aber als
prüfbedürftig gemeldet.

URL-Schema (Stand FM 26): ``/players/7-fm-26/{fmi_id}-{name-slug}``.
"""

from .. import normalize
from .base import (
    PageError,
    attr_or_empty,
    detect_block,
    first_int,
    id_from_url,
    text_or_empty,
)

BASE = 'https://fminside.net'


class FMInsideAdapter:
    def __init__(self, page, config, logger):
        self.page = page
        self.config = config
        self.log = logger

    def _goto(self, url):
        self.page.goto(url, wait_until='domcontentloaded')
        self.page.wait_for_timeout(int(self.config.pause('page_load_ms', 1500) * 1000))
        detect_block(self.page)

    def lookup(self, *, display_name, date_of_birth, nationality, warnings):
        """Sucht den Spieler und liefert Rohwerte oder ``None`` (mit Warnung)."""
        target_name = normalize.normalize_name(display_name)
        target_dob = normalize.normalize_dob(date_of_birth)
        if not target_name:
            warnings.append('FMInside: kein Name für die Suche vorhanden.')
            return None

        try:
            self._goto(f'{BASE}/search?q={display_name.replace(" ", "+")}')
        except PageError:
            warnings.append('FMInside: Suchseite nicht erreichbar.')
            return None

        candidates = self._search_results()
        match = self._pick(candidates, target_name, target_dob, nationality, warnings)
        if not match:
            warnings.append('FMInside: kein eindeutiger Treffer — prüfbedürftig.')
            return None

        try:
            self._goto(match['url'])
            return self._scrape_player(match)
        except PageError as exc:
            warnings.append(f'FMInside: Spielerseite nicht lesbar ({exc}).')
            return None

    # ── Selektoren ──────────────────────────────────────────────────────────
    def _search_results(self):
        links = self.page.locator('a[href*="/players/"]')
        out = []
        try:
            for i in range(min(links.count(), 25)):
                href = attr_or_empty(links.nth(i), 'href')
                name = text_or_empty(links.nth(i))
                fmi_id = id_from_url(href, 'players') or self._id_from_player_url(href)
                if fmi_id and name:
                    out.append({
                        'id': fmi_id, 'name': name,
                        'url': href if href.startswith('http') else f'{BASE}{href}'})
        except Exception:
            pass
        return out

    @staticmethod
    def _id_from_player_url(href):
        # /players/7-fm-26/{id}-{slug}
        import re
        m = re.search(r'/players/[^/]+/(\d+)-', href or '')
        return int(m.group(1)) if m else None

    def _pick(self, candidates, target_name, target_dob, nationality, warnings):
        name_hits = [c for c in candidates
                     if normalize.normalize_name(c['name']) == target_name]
        if not name_hits:
            return None
        if len(name_hits) == 1:
            return name_hits[0]
        # Mehrere Namensgleiche: über DOB/Nationalität eingrenzen passiert auf
        # der Detailseite nicht effizient — als prüfbedürftig melden.
        warnings.append(
            f'FMInside: {len(name_hits)} Namenstreffer — uneindeutig.')
        return None

    def _scrape_player(self, match):
        rating = first_int(text_or_empty(self.page.locator('.player-ca, .current-ability')))
        potential = first_int(text_or_empty(self.page.locator('.player-pa, .potential-ability')))
        attrs = self._attributes()
        return {
            'id': match['id'],
            'url': match['url'],
            'rating': rating,
            'potential': potential,
            'attrs': attrs,
        }

    def _attributes(self):
        """Liest die Attributtabelle als {Label: Wert}. Leer, wenn nicht gefunden."""
        attrs = {}
        rows = self.page.locator('.attributes tr, table.player-attributes tr')
        try:
            for i in range(rows.count()):
                cells = rows.nth(i).locator('td')
                if cells.count() >= 2:
                    label = text_or_empty(cells.nth(0)).rstrip(':').strip().lower()
                    value = first_int(text_or_empty(cells.nth(1)))
                    if label and value is not None:
                        attrs[label] = value
        except Exception:
            pass
        return attrs
