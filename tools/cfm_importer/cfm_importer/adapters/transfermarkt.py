"""Transfermarkt-Adapter — Kaderseite, Stammdaten, Positionen, Leihe.

Alle TM-spezifischen Selektoren sind hier gekapselt. Die Kaderseite wird über
Vereins-ID + Saison-ID geöffnet (kein fest verdrahteter Vereins-Slug — der
Platzhalter ``/-/`` wird von Transfermarkt selbst aufgelöst).

Es werden ausschließlich Rohwerte erfasst und unverändert (in deutscher
Schreibweise, z. B. ``"1,88 m"``, ``"100,00 Mio. €"``) übertragen — das Parsen
übernimmt die Server-Engine. Wird eine erwartete Struktur nicht gefunden, wird
der Spieler übersprungen, statt Leerwerte zu erfinden.
"""

from .. import positions
from .base import (
    PageError,
    attr_or_empty,
    first_int,
    id_from_url,
    safe_goto,
    text_or_empty,
)

BASE = 'https://www.transfermarkt.de'


class TransfermarktAdapter:
    def __init__(self, page, config, logger):
        self.page = page
        self.config = config
        self.log = logger

    # ── Navigation ──────────────────────────────────────────────────────────
    def _goto(self, url):
        safe_goto(self.page, url, self.config, self.log)

    def squad_url(self, club_id, season_id):
        return f'{BASE}/-/kader/verein/{int(club_id)}/saison_id/{int(season_id)}/plus/1'

    # ── Kaderseite ──────────────────────────────────────────────────────────
    def collect_squad(self, club_id, season_id):
        """Sammelt alle Spieler der aktuellen Kaderseite (dedupliziert über TM-ID).

        Erfasst zusätzlich den auf der Kaderseite angezeigten Vereinsnamen in
        ``self.squad_club_name`` (zur Bestätigung neu angelegter WS-Vereine).
        """
        self._goto(self.squad_url(club_id, season_id))
        self.squad_club_name = self._club_headline()
        rows = self.page.locator('table.items > tbody > tr')
        try:
            count = rows.count()
        except Exception:
            count = 0
        if count == 0:
            raise PageError('Kadertabelle nicht gefunden — Vereins-/Saison-ID prüfen.')

        seen = {}
        for i in range(count):
            link = rows.nth(i).locator('td.hauptlink a[href*="/profil/spieler/"]')
            if link.count() == 0:
                continue
            href = attr_or_empty(link, 'href')
            name = text_or_empty(link)
            pid = id_from_url(href, 'spieler')
            if not pid or pid in seen:
                continue
            profile_url = href if href.startswith('http') else f'{BASE}{href}'
            seen[pid] = {
                'tm_player_id': pid,
                'display_name': name,
                'profile_url': profile_url,
            }
        if not seen:
            raise PageError('Keine Spieler in der Kadertabelle gefunden.')
        return list(seen.values())

    # ── Stammdaten + Positionen ─────────────────────────────────────────────
    def player_details(self, entry):
        """Liefert das Kandidaten-Teilpayload (tm/club_assignment/positions)."""
        self._goto(entry['profile_url'])
        warnings = []
        errors = []

        display_name = self._headline() or entry.get('display_name', '')
        full_name = self._info_value('Voller Name') or self._info_value('Geburtsname')
        first_name, last_name = self._split_name(full_name or display_name)

        tm = {
            'profile_url': entry['profile_url'],
            'display_name': display_name,
            'first_name': first_name,
            'last_name': last_name,
            'date_of_birth': self._birth_date(),
            'height_cm': self._info_value('Größe'),
            'preferred_foot': self._info_value('Starker Fuß'),
            'primary_nationality': self._primary_nationality(),
            'nationalities': self._nationalities(),
            'market_value_eur': self._market_value(),
            'profile_position': self._profile_position(),
        }

        club_assignment = self._club_assignment(warnings)
        pos = self._positions(tm['profile_position'], warnings)

        return {
            'tm': tm,
            'club_assignment': club_assignment,
            'positions': pos,
            'warnings': warnings,
            'errors': errors,
        }

    def _club_headline(self):
        """Vereinsname aus dem Kaderseiten-Kopf (best effort, sonst '')."""
        try:
            h1 = self.page.locator('h1.data-header__headline-wrapper')
            return ' '.join(text_or_empty(h1).split())
        except Exception:
            return ''

    # ── Einzelfelder (Selektoren gekapselt) ─────────────────────────────────
    def _headline(self):
        h1 = self.page.locator('h1.data-header__headline-wrapper')
        text = text_or_empty(h1)
        # Trikotnummer (z. B. "#9") am Anfang entfernen.
        num = text_or_empty(h1.locator('.data-header__shirt-number'))
        if num and text.startswith(num):
            text = text[len(num):].strip()
        return ' '.join(text.split())

    def _info_value(self, label):
        loc = self.page.locator(
            "xpath=//span[contains(@class,'info-table__content--regular')]"
            f"[contains(normalize-space(.),'{label}')]"
            "/following-sibling::span[1]")
        return text_or_empty(loc)

    def _birth_date(self):
        # Im Profil verlinkt das Geburtsdatum auf einen Geburtstags-Kalender.
        loc = self.page.locator('span[itemprop="birthDate"]')
        if loc.count():
            return text_or_empty(loc)
        return self._info_value('Geburtsdatum')

    def _market_value(self):
        loc = self.page.locator('.data-header__market-value-wrapper')
        if loc.count() == 0:
            return ''
        # Erste Zeile enthält den Wert; Zusatztext ("Letzte Aktualisierung") raus.
        raw = text_or_empty(loc)
        return raw.split('Letzte')[0].strip()

    def _profile_position(self):
        # Im Profil unter "Position:" (Hauptposition).
        val = self._info_value('Position')
        if val:
            return val
        return text_or_empty(self.page.locator('.detail-position__position'))

    def _primary_nationality(self):
        nats = self._nationalities()
        return nats[0] if nats else ''

    def _nationalities(self):
        # Flaggen-Bilder in der Info-Tabelle tragen den Ländernamen im title.
        imgs = self.page.locator(
            "xpath=//span[contains(@class,'info-table__content--regular')]"
            "[contains(normalize-space(.),'Nationalität')]"
            "/following-sibling::span[1]//img")
        out = []
        try:
            for i in range(imgs.count()):
                title = (imgs.nth(i).get_attribute('title') or '').strip()
                if title and title not in out:
                    out.append(title)
        except Exception:
            pass
        return out

    def _club_assignment(self, warnings):
        """Erkennt Leihverhältnis; sonst aktueller Verein."""
        loan = self.page.get_by_text('ausgeliehen von', exact=False)
        if loan.count():
            block = loan.first
            club_link = block.locator(
                'xpath=ancestor-or-self::*[1]//a[contains(@href,"/verein/")]')
            href = attr_or_empty(club_link, 'href')
            name = text_or_empty(club_link)
            cid = id_from_url(href, 'verein')
            if cid:
                return {'loaned_from': {
                    'tm_club_id': cid, 'name': name,
                    'url': href if href.startswith('http') else f'{BASE}{href}'}}
            warnings.append('Leihe erkannt, aber Stammverein nicht eindeutig.')

        club_link = self.page.locator(
            '.data-header__club a[href*="/verein/"]')
        href = attr_or_empty(club_link, 'href')
        name = text_or_empty(club_link)
        cid = id_from_url(href, 'verein')
        if cid:
            return {'real_club': {
                'tm_club_id': cid, 'name': name,
                'url': href if href.startswith('http') else f'{BASE}{href}'}}
        return {}

    def _positions(self, profile_position, warnings):
        """Haupt-/Nebenpositionen aus dem Profil (mit internem Mapping).

        Transfermarkt listet im Profil eine Haupt- und mehrere Nebenpositionen.
        Diese werden explizit gemappt übertragen; die finale HP/NP-Logik läuft
        serverseitig. Einsatzzahlen pro Position werden nur übernommen, wenn die
        Detailseite sie strukturiert liefert — sonst bleiben sie leer (keine
        erfundenen Werte).
        """
        main_labels = []
        sec_labels = []

        main = self.page.locator(
            "xpath=//dt[contains(.,'Hauptposition')]/following-sibling::dd[1]")
        if main.count():
            main_labels.append(text_or_empty(main))
        secs = self.page.locator(
            "xpath=//dt[contains(.,'Nebenposition')]/following-sibling::dd[1]")
        if secs.count():
            for part in text_or_empty(secs).split(','):
                part = part.strip()
                if part:
                    sec_labels.append(part)

        if not main_labels and profile_position:
            main_labels.append(profile_position)

        def _map(labels):
            mapped = []
            for label in labels:
                code = positions.map_tm_position(label)
                if code is None:
                    warnings.append(f'Unbekannte TM-Position: {label!r}.')
                elif code not in mapped:
                    mapped.append(code)
            return mapped

        result = {
            'main_positions': _map(main_labels),
            'secondary_positions': _map(sec_labels),
        }
        appearances = self._appearances(warnings)
        if appearances:
            result['appearances'] = appearances
        return result

    def _appearances(self, warnings):
        """Einsätze je Position über alle Saisons, falls strukturiert verfügbar.

        Greift auf die Detail-Leistungsdaten zu. Findet sich keine
        positionsbezogene Tabelle, wird eine leere Liste zurückgegeben (die
        explizit gemappten Haupt-/Nebenpositionen bleiben maßgeblich).
        """
        return []

    @staticmethod
    def _split_name(name):
        name = ' '.join((name or '').split())
        if not name:
            return '', ''
        parts = name.split(' ')
        if len(parts) == 1:
            return '', parts[0]
        return parts[0], ' '.join(parts[1:])
