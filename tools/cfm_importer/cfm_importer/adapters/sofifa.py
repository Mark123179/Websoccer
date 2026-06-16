"""SoFIFA-Adapter — Match über Name + Geburtsdatum, Rohwerte.

Selektoren gekapselt. Das Matching ist bewusst zweistufig:

1. **Namens-Vorfilter (tolerant).** SoFIFA-Trefferlisten zeigen oft Kurz-/
   Abkürzungsnamen (z. B. „L. Messi" statt „Lionel Messi"). Ein reiner
   Gleichheitsvergleich der buchstabennormalisierten Namen scheitert dann und
   das Profil wird nie geöffnet. Daher werden Kandidaten tolerant vorgefiltert
   (gleicher Nachname + verträglicher Vorname/Initiale).
2. **Bestätigung über das Geburtsdatum.** Nur ein per Geburtsdatum bestätigter,
   eindeutiger Treffer wird übernommen — es wird **nicht** geraten. Lässt sich
   das Geburtsdatum nicht lesen und bleibt genau **ein** plausibler Kandidat,
   wird dieser mit einer ausdrücklichen Warnung („bitte prüfen") übernommen,
   weil SoFIFA optional ist und in der Kontrollphase ohnehin gesichtet wird.

Fehlendes SoFIFA blockiert den Import NICHT (kein Eintrag wird übertragen).
Getrennte Rohwerte für Feldspieler und Torhüter werden über die Attributnamen
abgebildet.
"""

import re

from .. import normalize
from .base import (
    PageError,
    attr_or_empty,
    first_int,
    safe_goto,
    text_or_empty,
)

BASE = 'https://sofifa.com'

# Wie viele plausible Kandidaten höchstens geöffnet werden, um sie über das
# Geburtsdatum zu bestätigen. Trefferlisten enthalten in der Praxis sehr wenige
# Namensgleiche; eine kleine Obergrenze hält den Lauf schnell.
MAX_PROFILE_CHECKS = 4

_MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def _first_dob(text):
    """Erstes plausibles Geburtsdatum aus Text auf ``YYYY-MM-DD`` normalisiert.

    Erkennt ISO (``YYYY-MM-DD``), tagweise Formate (``TT.MM.JJJJ`` mit ``.``,
    ``-`` oder ``/``) sowie englische Monatsschreibweisen, wie SoFIFA sie nutzt
    (``Dec 28, 2002`` bzw. ``28 Dec 2002``). Gibt ``''`` zurück, wenn nichts
    Eindeutiges gefunden wird (kein Raten).
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
    # Englisch: „Dec 28, 2002"
    m = re.search(r'([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})', text)
    if m:
        mo = _MONTHS.get(m.group(1)[:3].lower())
        if mo:
            return f'{int(m.group(3)):04d}-{mo:02d}-{int(m.group(2)):02d}'
    # Englisch: „28 Dec 2002"
    m = re.search(r'(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})', text)
    if m:
        mo = _MONTHS.get(m.group(2)[:3].lower())
        if mo:
            return f'{int(m.group(3)):04d}-{mo:02d}-{int(m.group(1)):02d}'
    return ''


def _name_tokens(value):
    """Zerlegt einen Namen in buchstabennormalisierte Tokens.

    Jedes Token wird für sich nach denselben Regeln wie ``normalize_name``
    behandelt (Diakritika/Sonderzeichen entfernt). Punkte trennen Initialen
    (``L.`` → ``l``). Leere Tokens entfallen.
    """
    raw = re.split(r'[\s.]+', value or '')
    out = []
    for part in raw:
        tok = normalize.normalize_name(part)
        if tok:
            out.append(tok)
    return out


def _name_matches(result_name, target_name):
    """Tolerant: gleicher Nachname + verträglicher Vorname/Initiale.

    Deckt Kurz-/Abkürzungsnamen aus der SoFIFA-Trefferliste ab, ohne offenkundig
    Fremde zu akzeptieren. Die endgültige Eindeutigkeit stellt das Geburtsdatum
    her — dieser Vorfilter darf also bewusst etwas großzügig sein.
    """
    rt = _name_tokens(result_name)
    tt = _name_tokens(target_name)
    if not rt or not tt:
        return False
    # Exakte (verkettete) Gleichheit zuerst — günstigster, sicherster Fall.
    if ''.join(rt) == ''.join(tt):
        return True
    # Einzeltoken-Seite (Mononym/Kurzname, z. B. „Vinicius"): Treffer, wenn das
    # Token mit dem Vor- oder Nachnamen der anderen Seite übereinstimmt.
    if len(rt) == 1 or len(tt) == 1:
        single = rt[0] if len(rt) == 1 else tt[0]
        other = tt if len(rt) == 1 else rt
        return single in (other[0], other[-1])
    # Mehrtoken: Nachnamen müssen übereinstimmen.
    if rt[-1] != tt[-1]:
        return False
    # Vornamen verträglich: gleich oder eine Seite ist eine passende Initiale.
    rf, tf = rt[0], tt[0]
    if rf == tf:
        return True
    if len(rf) == 1 or len(tf) == 1:
        return rf[0] == tf[0]
    return False


class SoFIFAAdapter:
    def __init__(self, page, config, logger):
        self.page = page
        self.config = config
        self.log = logger

    def _goto(self, url):
        safe_goto(self.page, url, self.config, self.log)

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
        plausible = self._plausible(candidates, display_name, target_name)
        if not plausible:
            # SoFIFA ist optional — nur Hinweis, kein Fehler.
            warnings.append('SoFIFA: kein Namenstreffer (optional).')
            return None

        return self._confirm_and_scrape(plausible, target_dob, warnings)

    # ── Auswahl/Bestätigung ─────────────────────────────────────────────────
    def _plausible(self, candidates, display_name, target_name):
        """Tolerant gefilterte, nach ID deduplizierte Kandidatenliste.

        Fällt der tolerante Filter leer aus, greift als Rückfall die strikte
        (buchstabennormalisierte) Gleichheit — so geht kein offensichtlicher
        Treffer verloren, falls die Tokenisierung einen Sonderfall verfehlt.
        """
        hits = [c for c in candidates if _name_matches(c['name'], display_name)]
        if not hits:
            hits = [c for c in candidates
                    if normalize.normalize_name(c['name']) == target_name]
        seen, out = set(), []
        for c in hits:
            if c['id'] in seen:
                continue
            seen.add(c['id'])
            out.append(c)
        return out

    def _confirm_and_scrape(self, plausible, target_dob, warnings):
        """Öffnet plausible Profile und bestätigt sie über das Geburtsdatum."""
        results = []  # (candidate, scraped) in Listenreihenfolge
        for cand in plausible[:MAX_PROFILE_CHECKS]:
            try:
                self._goto(cand['url'])
            except PageError:
                continue
            results.append((cand, self._scrape_player(cand)))

        if not results:
            warnings.append('SoFIFA: Spielerseite nicht lesbar (optional).')
            return None

        if target_dob:
            confirmed = [d for _, d in results if d.get('dob') == target_dob]
            if len(confirmed) == 1:
                return confirmed[0]
            if len(confirmed) > 1:
                warnings.append('SoFIFA: mehrere Treffer mit gleichem '
                                'Geburtsdatum — uneindeutig (optional).')
                return None
            # Kein per Geburtsdatum bestätigter Treffer.
            if len(results) == 1:
                only = results[0][1]
                if only.get('dob'):
                    warnings.append('SoFIFA: Geburtsdatum weicht ab — '
                                    'übersprungen (optional).')
                    return None
                warnings.append('SoFIFA: Geburtsdatum nicht lesbar — Treffer '
                                'per Name übernommen, bitte prüfen.')
                return only
            warnings.append('SoFIFA: kein per Geburtsdatum bestätigter Treffer '
                            '(optional).')
            return None

        # Kein Ziel-Geburtsdatum vorhanden → nur ein eindeutiger Namenstreffer.
        if len(results) == 1:
            warnings.append('SoFIFA: kein Geburtsdatum zum Abgleich — Treffer '
                            'per Name übernommen, bitte prüfen.')
            return results[0][1]
        warnings.append('SoFIFA: mehrere Namenstreffer ohne Geburtsdatum — '
                        'uneindeutig (optional).')
        return None

    # ── Selektoren ──────────────────────────────────────────────────────────
    def _search_results(self):
        """Liest die Trefferzeilen (ID, angezeigter Name, URL).

        Bevorzugt die Spieler-Links innerhalb der Ergebnistabelle; fällt diese
        Struktur weg, greift ein breiterer Selektor als Rückfall.
        """
        for selector in ('table tbody tr a[href*="/player/"]',
                         'a[href*="/player/"]'):
            out = self._collect_links(selector)
            if out:
                return out
        return []

    def _collect_links(self, selector):
        links = self.page.locator(selector)
        out = []
        try:
            for i in range(min(links.count(), 30)):
                link = links.nth(i)
                href = attr_or_empty(link, 'href')
                name = text_or_empty(link) or attr_or_empty(link, 'aria-label')
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

    def _scrape_player(self, match):
        rating = first_int(text_or_empty(
            self.page.locator('.player-overall, [data-overall]')))
        potential = first_int(text_or_empty(
            self.page.locator('.player-potential, [data-potential]')))
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
        for sel in ('.player-info', '.profile', '.player-profile',
                    '.player-header', '.bp3-text-muted'):
            dob = _first_dob(text_or_empty(self.page.locator(sel)))
            if dob:
                return dob
        try:
            body = self.page.locator('body').inner_text()
        except Exception:
            body = ''
        return _first_dob(body)

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
