"""FMInside-Adapter — eindeutige Zuordnung über FM-ID bzw. Name + Geburtsdatum.

Selektoren sind hier gekapselt. **Namen sind nicht eindeutig** und werden daher
niemals allein akzeptiert: Ein per Namenssuche gefundener Treffer gilt nur als
gültig, wenn das **Geburtsdatum** auf der Detailseite übereinstimmt. Ist eine
**FM-ID** bekannt, wird direkt die kanonische Spielerseite geöffnet (kein Raten
über den Namen). Mehrdeutige oder unbestätigte Fälle werden als *prüfbedürftig*
gemeldet — niemals wird ein falscher Treffer erzwungen. Fehlendes FMInside
blockiert den Import NICHT.

URL-Schema: ``/players/{db-version}/{fmi_id}-{name-slug}`` (z. B.
``/players/7-fm-26/28049320-harry-kane``). Der DB-Versions-Pfad ist Pflicht
(``7-fm-26`` = FM26.2); der Slug ist kosmetisch, muss aber vorhanden sein — ohne
Slug liefert die Seite 404. Maßgeblich ist die ID im Pfad.
"""

import re

from .. import normalize
from .base import (
    PageError,
    attr_or_empty,
    first_int,
    id_from_url,
    safe_goto,
    text_or_empty,
)

BASE = 'https://fminside.net'

# Höchstzahl an Detailseiten, die zur Geburtsdatums-Bestätigung geöffnet werden.
MAX_DETAIL_CHECKS = 5

# DB-Versions-Pfade für die kanonische Spieler-URL. ``7-fm-26`` = FM26.2 (aktuelle
# Standardversion). Wird der Reihe nach probiert, falls eine ID in einer älteren
# Datenbank liegt (mirror von populate_positions_fmi).
FM_VERSIONS = ('7-fm-26', '7-fm-25', '7-fm-27', '7-fm-28')


def _first_dob(text):
    """Erstes plausibles Datum aus Text auf ``YYYY-MM-DD`` normalisiert.

    Erkennt ISO (``YYYY-MM-DD``) sowie tagweise Formate mit ``.``, ``-`` oder
    ``/`` (``TT.MM.JJJJ``). Gibt ``''`` zurück, wenn nichts Eindeutiges gefunden
    wird (kein Raten).
    """
    if not text:
        return ''
    m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
    if m:
        y, mo, d = m.groups()
        return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'
    m = re.search(r'(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})', text)
    if m:
        d, mo, y = m.groups()
        return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'
    return ''


def _name_slug(display_name):
    """Baut einen URL-Slug ``vorname-name`` aus dem Anzeigenamen."""
    import unicodedata
    value = unicodedata.normalize('NFKD', display_name or '')
    value = value.encode('ASCII', 'ignore').decode('ASCII').lower()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')


class FMInsideAdapter:
    def __init__(self, page, config, logger):
        self.page = page
        self.config = config
        self.log = logger

    def _goto(self, url):
        safe_goto(self.page, url, self.config, self.log)

    def lookup(self, *, display_name, date_of_birth, nationality, warnings,
               fmi_id=None):
        """Liefert FMInside-Rohwerte oder ``None`` (mit Warnung).

        Reihenfolge: bekannte **FM-ID** → direkter, eindeutiger Aufruf. Sonst
        **Namenssuche**, deren Treffer erst über das **Geburtsdatum** auf der
        Detailseite bestätigt werden muss — Namen sind nicht eindeutig und
        werden nie allein akzeptiert.
        """
        if fmi_id:
            return self._lookup_by_id(fmi_id, display_name, warnings)

        target_name = normalize.normalize_name(display_name)
        target_dob = normalize.normalize_dob(date_of_birth)
        if not target_name:
            warnings.append('FMInside: kein Name für die Suche vorhanden.')
            return None
        if not target_dob:
            warnings.append('FMInside: kein Geburtsdatum vorhanden — keine '
                            'eindeutige Zuordnung möglich (FM-ID manuell setzen).')
            return None

        try:
            self._goto(f'{BASE}/search?q={display_name.replace(" ", "+")}')
        except PageError:
            warnings.append('FMInside: Suchseite nicht erreichbar.')
            return None

        name_hits = [c for c in self._search_results()
                     if normalize.normalize_name(c['name']) == target_name]
        if not name_hits:
            warnings.append('FMInside: kein Namenstreffer — prüfbedürftig.')
            return None

        if len(name_hits) > MAX_DETAIL_CHECKS:
            warnings.append(
                f'FMInside: {len(name_hits)} Namenstreffer — nur die ersten '
                f'{MAX_DETAIL_CHECKS} werden per Geburtsdatum geprüft.')

        # Namen sind nicht eindeutig: jeden Treffer per Geburtsdatum bestätigen.
        confirmed = []
        for cand in name_hits[:MAX_DETAIL_CHECKS]:
            raw = self._open_and_scrape(cand, warnings)
            if raw and raw.get('dob') and raw['dob'] == target_dob:
                confirmed.append(raw)

        if not confirmed:
            warnings.append('FMInside: kein per Geburtsdatum bestätigter Treffer '
                            '— prüfbedürftig (FM-ID manuell setzen).')
            return None
        if len(confirmed) > 1:
            warnings.append('FMInside: mehrere per Geburtsdatum bestätigte '
                            'Treffer — uneindeutig.')
            return None
        return confirmed[0]

    # ── Selektoren ──────────────────────────────────────────────────────────
    def _search_results(self):
        links = self.page.locator('a[href*="/players/"]')
        out = []
        try:
            for i in range(min(links.count(), 25)):
                href = attr_or_empty(links.nth(i), 'href')
                name = text_or_empty(links.nth(i))
                fmi_id = self._id_from_player_url(href)
                if fmi_id and name:
                    out.append({
                        'id': fmi_id, 'name': name,
                        'url': href if href.startswith('http') else f'{BASE}{href}'})
        except Exception:
            pass
        return out

    @staticmethod
    def _id_from_player_url(href):
        """Extrahiert die FM-ID aus beiden URL-Schemata.

        Neu: ``/players/7-fm-26/{id}-{slug}`` → ``{id}``
        Alt: ``/players/{id}-{slug}``         → ``{id}``

        Wichtig: zuerst das zweisegmentige Schema prüfen, sonst würde das
        einsegmentige Muster fälschlich die DB-Version (z. B. ``7``) greifen.
        """
        href = href or ''
        m = re.search(r'/players/[^/]+/(\d+)-', href)
        if m:
            return int(m.group(1))
        m = re.search(r'/players/(\d+)-', href)
        return int(m.group(1)) if m else None

    # ── Direkter Zugriff über bekannte FM-ID ────────────────────────────────
    @staticmethod
    def _clean_fm_id(raw):
        """Bereinigt eine FM-ID zu reinen Ziffern.

        Entfernt BOM/Leerzeichen und einen ``.0``-Suffix (Float-Export aus
        Tabellen), damit Werte wie ``"2000262919.0"``, ``" 2000262919 "`` oder
        ``"\ufeff2000262919"`` korrekt verarbeitet werden. Wirft ``ValueError``
        bei leerem oder nicht-numerischem Wert.
        """
        fm_id = str(raw or '').replace('\ufeff', '').strip()
        if fm_id.endswith('.0'):
            fm_id = fm_id[:-2]
        if not fm_id.isdigit():
            raise ValueError(f'Ungültige FM-ID: {raw!r}')
        return fm_id

    def _lookup_by_id(self, fmi_id, display_name, warnings):
        """Öffnet die kanonische Seite zur bekannten FM-ID — eindeutig, kein Raten.

        Probiert die DB-Versions-Pfade der Reihe nach (FM26 zuerst). Der Slug ist
        kosmetisch (irgendein nicht-leerer Wert genügt), entscheidend ist die ID
        im Pfad. Nach dem Laden wird geprüft, dass die Nummer in der geöffneten
        URL mit der gesuchten FM-ID übereinstimmt.
        """
        try:
            uid = self._clean_fm_id(fmi_id)
        except ValueError:
            warnings.append(f'FMInside: ungültige FM-ID {fmi_id!r} — übersprungen.')
            return None

        slug = _name_slug(display_name) or 'player'
        target = int(uid)
        last_exc = None
        for version in FM_VERSIONS:
            url = f'{BASE}/players/{version}/{uid}-{slug}'
            try:
                self._goto(url)
            except PageError as exc:
                last_exc = exc
                continue  # 404 → nächste DB-Version probieren

            opened = (self._id_from_player_url(getattr(self.page, 'url', ''))
                      or self._id_from_player_url(url))
            if opened != target:
                warnings.append(
                    f'FMInside: FM-ID-Abweichung (gesucht {uid}, Seite {opened}) '
                    '— prüfbedürftig.')
                return None
            return self._scrape_player({'id': target, 'url': url})

        warnings.append(
            f'FMInside: keine Seite zu FM-ID {uid} gefunden ({last_exc}).')
        return None

    def _open_and_scrape(self, cand, warnings):
        """Öffnet einen Suchtreffer und liefert dessen Rohwerte (inkl. DOB)."""
        try:
            self._goto(cand['url'])
        except PageError as exc:
            warnings.append(f'FMInside: Detailseite nicht lesbar ({exc}).')
            return None
        return self._scrape_player(cand)

    def _scrape_player(self, match):
        rating = first_int(text_or_empty(self.page.locator('.player-ca, .current-ability')))
        potential = first_int(text_or_empty(self.page.locator('.player-pa, .potential-ability')))
        attrs = self._attributes()
        return {
            'id': match['id'],
            'url': match['url'],
            'dob': self._scrape_dob(),
            'rating': rating,
            'potential': potential,
            'attrs': attrs,
        }

    def _scrape_dob(self):
        """Liest das Geburtsdatum defensiv als ``YYYY-MM-DD`` (sonst '')."""
        for sel in ('.player-info', '.player-details', '.player-header',
                    '.profile', '.player-profile'):
            dob = _first_dob(text_or_empty(self.page.locator(sel)))
            if dob:
                return dob
        try:
            body = self.page.locator('body').inner_text()
        except Exception:
            body = ''
        return _first_dob(body)

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
