"""FMInside-Adapter — eindeutige Zuordnung ausschließlich über die FM-ID.

Selektoren sind hier gekapselt. **Namen sind nicht eindeutig**, und FMInside
bietet keine zuverlässig nutzbare öffentliche Namenssuche (die frühere Route
``/search?q=`` existiert nicht mehr und liefert **404**). Daher gilt strikt:
ist eine **FM-ID** bekannt, wird direkt die kanonische Spielerseite geöffnet
(kein Raten über den Namen); fehlt die FM-ID, wird der Fall sauber als
*prüfbedürftig* gemeldet (FM-ID manuell setzen) — es wird **nicht** zu einer
nicht existierenden Suchseite navigiert. Fehlendes FMInside blockiert den
Import NICHT.

URL-Schema: Die einsegmentige URL ``/players/{fmi_id}-{slug}`` wird von FMInside
automatisch auf die **neueste** kanonische DB-Version umgeleitet (z. B.
``/players/7-fm262/28049320-harry-kane``). So muss keine Version hartkodiert
werden — es gilt stets die aktuellste. Der Slug ist kosmetisch (irgendein
nicht-leerer Wert genügt); ohne Slug landet man auf der Spielerliste. Maßgeblich
ist die ID in der **finalen** (umgeleiteten) URL.
"""

import re

from .base import (
    PageError,
    first_int,
    safe_goto,
    text_or_empty,
)

BASE = 'https://fminside.net'

# Platzhalter-Slug für die einsegmentige Spieler-URL. Die ID ist bereits
# eindeutig; FMInside verlangt aber technisch ein nicht-leeres Segment nach dem
# Bindestrich (``/players/{id}`` ohne Slug leitet auf die Spielerliste um). Der
# Inhalt ist irrelevant — die Seite leitet ohnehin auf den kanonischen Slug um.
PLACEHOLDER_SLUG = 'player'


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

        Ausschließlich über die bekannte **FM-ID** (direkter, eindeutiger
        Aufruf der kanonischen Spielerseite). Fehlt die FM-ID, gibt es keinen
        zuverlässigen öffentlichen Suchweg — FMInside bietet keine nutzbare
        Namens-Such-URL (die frühere ``/search?q=``-Route liefert 404). Statt
        auf eine nicht existierende Seite zu navigieren, wird der Fall sauber
        als prüfbedürftig gemeldet (FM-ID manuell setzen).
        """
        if fmi_id:
            return self._lookup_by_id(fmi_id, warnings)

        warnings.append('FMInside: keine FM-ID bekannt — keine zuverlässige '
                        'Namenssuche verfügbar; prüfbedürftig (FM-ID manuell '
                        'setzen).')
        return None

    # ── Selektoren ──────────────────────────────────────────────────────────
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

    def _lookup_by_id(self, fmi_id, warnings):
        """Öffnet die kanonische Seite zur bekannten FM-ID — eindeutig, kein Raten.

        Nutzt die einsegmentige URL ``/players/{id}-{slug}``; FMInside leitet
        automatisch auf die **neueste** DB-Version um (keine Version hartkodiert).
        Die ID ist bereits eindeutig — der Slug ist nur ein Platzhalter
        (``PLACEHOLDER_SLUG``), den die Route technisch verlangt; sein Inhalt ist
        irrelevant. Nach dem Laden wird geprüft, dass die Nummer in der
        **finalen** URL mit der gesuchten FM-ID übereinstimmt — sonst gilt der
        Treffer als prüfbedürftig.
        """
        try:
            uid = self._clean_fm_id(fmi_id)
        except ValueError:
            warnings.append(f'FMInside: ungültige FM-ID {fmi_id!r} — übersprungen.')
            return None

        url = f'{BASE}/players/{uid}-{PLACEHOLDER_SLUG}'
        try:
            self._goto(url)
        except PageError as exc:
            warnings.append(
                f'FMInside: Spielerseite zu FM-ID {uid} nicht lesbar ({exc}).')
            return None

        target = int(uid)
        final_url = getattr(self.page, 'url', '') or url
        opened = self._id_from_player_url(final_url)
        if opened is None:
            warnings.append(
                f'FMInside: keine Spielerseite zu FM-ID {uid} '
                '(Weiterleitung auf Liste) — prüfbedürftig.')
            return None
        if opened != target:
            warnings.append(
                f'FMInside: FM-ID-Abweichung (gesucht {uid}, Seite {opened}) '
                '— prüfbedürftig.')
            return None
        return self._scrape_player({'id': target, 'url': final_url})

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
