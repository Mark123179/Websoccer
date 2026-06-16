"""Zuordnung des Transfermarkt-Kaders zum Websoccer-Kader per Name + Geburtsdatum.

Beim Auftrags-Claim liefert der Webserver den Kader des Ziel-Vereins inklusive
``fm_inside_id`` (aus dem CSV-Import). Da Transfermarkt keine FMInside-IDs kennt,
ordnet diese Klasse jeden TM-Spieler über seinen **normalisierten Namen + sein
Geburtsdatum** einer ``fm_inside_id`` zu. Erst diese ID ermöglicht den
eindeutigen FMInside-Lookup über die Unique ID.

Eindeutigkeit geht vor Trefferquote: Ein per Name mehrdeutiger Fall (zwei
Spieler gleichen Namens) wird ohne passendes Geburtsdatum NICHT zugeordnet, und
widersprechende Geburtsdaten führen ebenfalls zu keinem Treffer — so wird ein
falscher FMInside-Treffer vermieden.
"""

from . import normalize


class RosterMatcher:
    """Index über (Name, Geburtsdatum) → ``fm_inside_id`` mit sicherem Fallback."""

    def __init__(self, roster):
        self._by_name_dob = {}   # (name, dob) -> fm_inside_id
        self._single = {}        # name -> (fm_inside_id, dob)  (nur eindeutige Namen)
        ambiguous_names = set()
        ambiguous_keys = set()   # (name, dob) mit widersprüchlichen IDs

        for entry in roster or []:
            fm_id = entry.get('fm_inside_id')
            if not fm_id:
                continue
            name = normalize.normalize_name(
                f"{entry.get('first_name', '')} {entry.get('last_name', '')}")
            if not name:
                continue
            dob = normalize.normalize_dob(entry.get('date_of_birth', ''))
            if dob:
                key = (name, dob)
                if key in self._by_name_dob and self._by_name_dob[key] != fm_id:
                    # Gleicher Name + gleiches Geburtsdatum, aber andere ID →
                    # niemals raten (kein last-write-wins).
                    ambiguous_keys.add(key)
                else:
                    self._by_name_dob[key] = fm_id
            if name in self._single and self._single[name][0] != fm_id:
                ambiguous_names.add(name)
            else:
                self._single[name] = (fm_id, dob)

        for key in ambiguous_keys:
            self._by_name_dob.pop(key, None)
        for name in ambiguous_names:
            self._single.pop(name, None)

    def __len__(self):
        return len(self._single)

    def match(self, display_name, date_of_birth=''):
        """Liefert die ``fm_inside_id`` oder ``None`` (kein eindeutiger Treffer).

        Reihenfolge: exakter Name+Geburtsdatum-Treffer; sonst eindeutiger
        Namens-Treffer, sofern die Geburtsdaten sich nicht widersprechen.
        """
        name = normalize.normalize_name(display_name)
        if not name:
            return None

        dob = normalize.normalize_dob(date_of_birth)
        if dob:
            hit = self._by_name_dob.get((name, dob))
            if hit:
                return hit

        single = self._single.get(name)
        if not single:
            return None
        fm_id, roster_dob = single
        if dob and roster_dob and dob != roster_dob:
            return None  # Geburtsdaten widersprechen sich → kein Treffer
        return fm_id
