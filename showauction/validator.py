"""16-Achsen-Validator der Show-Auktion (Spec §5, §6.1) — handgerollt, deutsch.

validate_config(config) prüft Typen, Wertebereiche und Querbezüge der
16 Regel-Achsen und liefert eine normalisierte Kopie zurück. Fehler
werden GESAMMELT als ValidationError mit deutschen Meldungen geworfen —
der Creator sieht alle Probleme auf einmal, nicht nur das erste.

Unbekannte Schlüssel sind hart verboten (Tippfehler dürfen nicht still
verschwinden — Lehre aus dem Stadionumfeld-Whitelisting).
"""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

GEBOTSRICHTUNGEN = ('aufsteigend', 'verdeckt', 'fallend', 'fest')
SICHTBARKEITEN = (
    'hoechstgebot_und_bieter', 'nur_hoechstgebot', 'nur_gebotsanzahl', 'nichts',
)
ENDEBEDINGUNGEN = ('deadline', 'haltezeit', 'erster_zuschlag', 'preisboden')
ZUSCHLAGSPREISE = ('eigenes_gebot', 'zweithoechstes_plus_erhoehung')
GEWINNERERMITTLUNGEN = (
    'hoechstes_gebot', 'naechstliegend_verborgenes_ziel', 'erster_zuschlag',
)
RESERVIERUNGSFREIGABEN = (
    'bei_ueberbietung', 'bei_auktionsende', 'sofortige_buchung',
)
BEDINGUNGSARTEN = (
    'max_mw_schnitt', 'coins', 'freie_kaderplaetze', 'mindestkontostand', 'liga',
)

ERLAUBTE_KEYS = {
    'gebotsrichtung', 'sichtbarkeit', 'endebedingung', 'verlaengerung',
    'haltezeit_verlauf', 'gebote_pro_manager', 'gebot_aenderbar',
    'mindesterhoehung', 'startpreis', 'preisverfall', 'zuschlagspreis',
    'teilnahmebedingungen', 'darstellung', 'maximallaufzeit',
    'gewinnerermittlung', 'reservierungsfreigabe',
    # Begleitparameter
    'laufzeit_minuten',   # Pflicht bei endebedingung=deadline
    'korridor',           # Pflicht bei gewinnerermittlung=naechstliegend_…
}


def _num(value):
    """Zahl (int/float/Decimal/Zahl-String) → Decimal, sonst None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if isinstance(value, str):
        try:
            return Decimal(value.replace(',', '.'))
        except InvalidOperation:
            return None
    return None


def _pos_int(value):
    """Positive Ganzzahl oder None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit() and int(value) > 0:
        return int(value)
    return None


def validate_config(config):  # noqa: C901 — bewusst ein linearer Regelkatalog
    if not isinstance(config, dict):
        raise ValidationError(['Die Konfiguration muss ein Objekt (JSON-Dict) sein.'])

    fehler = []
    cfg = dict(config)

    unbekannt = sorted(set(cfg) - ERLAUBTE_KEYS)
    if unbekannt:
        fehler.append(
            'Unbekannte Schlüssel: ' + ', '.join(unbekannt)
            + '. Erlaubt sind nur die 16 Regel-Achsen und ihre Begleitparameter.'
        )

    # ── Achse 1: Gebotsrichtung ──────────────────────────────────────────
    richtung = cfg.get('gebotsrichtung')
    if richtung not in GEBOTSRICHTUNGEN:
        fehler.append(
            "Achse 1 (gebotsrichtung): Pflicht — eine von "
            + ', '.join(GEBOTSRICHTUNGEN) + '.'
        )

    # ── Achse 2: Sichtbarkeit ────────────────────────────────────────────
    sicht = cfg.get('sichtbarkeit')
    if sicht not in SICHTBARKEITEN:
        fehler.append(
            'Achse 2 (sichtbarkeit): Pflicht — eine von '
            + ', '.join(SICHTBARKEITEN) + '.'
        )

    # ── Achse 3: Endebedingung ───────────────────────────────────────────
    ende = cfg.get('endebedingung')
    if ende not in ENDEBEDINGUNGEN:
        fehler.append(
            'Achse 3 (endebedingung): Pflicht — eine von '
            + ', '.join(ENDEBEDINGUNGEN) + '.'
        )

    # ── Achse 4: Verlängerung ────────────────────────────────────────────
    verl = cfg.setdefault('verlaengerung', 'aus')
    if verl != 'aus':
        if not (isinstance(verl, dict) and set(verl) == {'minuten', 'fenster'}
                and _pos_int(verl.get('minuten')) and _pos_int(verl.get('fenster'))):
            fehler.append(
                "Achse 4 (verlaengerung): 'aus' oder "
                "{minuten: >0, fenster: >0} (beides ganze Minuten)."
            )
        elif ende != 'deadline':
            fehler.append(
                'Achse 4 (verlaengerung): nur bei endebedingung=deadline erlaubt.'
            )

    # ── Achse 5: Haltezeit-Verlauf ───────────────────────────────────────
    hv = cfg.get('haltezeit_verlauf')
    if ende == 'haltezeit':
        ok = False
        if isinstance(hv, dict) and set(hv) == {'konstant'}:
            ok = _num(hv.get('konstant')) is not None and _num(hv['konstant']) > 0
        elif isinstance(hv, dict) and set(hv) == {'degressiv'}:
            stufen = hv.get('degressiv')
            ok = (isinstance(stufen, list) and len(stufen) >= 1
                  and all(_num(s) is not None and _num(s) > 0 for s in stufen))
        if not ok:
            fehler.append(
                'Achse 5 (haltezeit_verlauf): bei endebedingung=haltezeit Pflicht — '
                "{konstant: Stunden > 0} oder {degressiv: [Stundenliste]}."
            )
    elif hv is not None:
        fehler.append(
            'Achse 5 (haltezeit_verlauf): nur bei endebedingung=haltezeit erlaubt.'
        )

    # ── Achse 6: Gebote pro Manager ──────────────────────────────────────
    gebote = cfg.get('gebote_pro_manager')
    gebote_ok = (
        gebote in ('unbegrenzt', 'genau_1')
        or (isinstance(gebote, dict) and set(gebote) == {'max'}
            and _pos_int(gebote.get('max')))
    )
    if not gebote_ok:
        fehler.append(
            "Achse 6 (gebote_pro_manager): 'unbegrenzt', 'genau_1' oder {max: N ≥ 1}."
        )

    # ── Achse 7: Gebot änderbar ──────────────────────────────────────────
    aenderbar = cfg.setdefault('gebot_aenderbar', 'nein')
    if aenderbar not in ('ja', 'nein'):
        fehler.append("Achse 7 (gebot_aenderbar): 'ja' oder 'nein'.")
    elif aenderbar == 'ja' and gebote == 'unbegrenzt':
        fehler.append(
            'Achse 7 (gebot_aenderbar): änderbar=ja ist nur sinnvoll, wenn die '
            'Gebotsanzahl begrenzt ist (Achse 6 ≠ unbegrenzt).'
        )

    # ── Achse 8: Mindesterhöhung ─────────────────────────────────────────
    erh = cfg.setdefault('mindesterhoehung', 'keine')
    if erh != 'keine':
        ok = False
        if isinstance(erh, dict) and set(erh) == {'fix'}:
            ok = _num(erh.get('fix')) is not None and _num(erh['fix']) > 0
        elif isinstance(erh, dict) and set(erh) == {'prozent'}:
            ok = _num(erh.get('prozent')) is not None and _num(erh['prozent']) > 0
        elif isinstance(erh, dict) and set(erh) == {'max_fix_prozent'}:
            mfp = erh.get('max_fix_prozent')
            ok = (isinstance(mfp, dict) and set(mfp) == {'fix', 'prozent', 'rundung'}
                  and _num(mfp.get('fix')) is not None and _num(mfp['fix']) > 0
                  and _num(mfp.get('prozent')) is not None and _num(mfp['prozent']) > 0
                  and _num(mfp.get('rundung')) is not None and _num(mfp['rundung']) >= 0)
        if not ok:
            fehler.append(
                "Achse 8 (mindesterhoehung): 'keine', {fix: X}, {prozent: P} oder "
                '{max_fix_prozent: {fix, prozent, rundung}}.'
            )

    # ── Achse 9: Startpreis ──────────────────────────────────────────────
    sp = cfg.get('startpreis')
    sp_ok = (
        sp == 'frei'
        or (isinstance(sp, dict) and set(sp) == {'absolut'}
            and _num(sp.get('absolut')) is not None and _num(sp['absolut']) > 0)
        or (isinstance(sp, dict) and set(sp) == {'prozent_mw'}
            and _num(sp.get('prozent_mw')) is not None and _num(sp['prozent_mw']) > 0)
    )
    if not sp_ok:
        fehler.append(
            "Achse 9 (startpreis): Pflicht — 'frei', {absolut: X} oder {prozent_mw: P}."
        )

    # ── Achse 10: Preisverfall ───────────────────────────────────────────
    pv = cfg.setdefault('preisverfall', 'aus')
    if richtung == 'fallend':
        ok = (isinstance(pv, dict)
              and set(pv) == {'schritt_prozent', 'intervall_minuten', 'boden_prozent_mw'}
              and _num(pv.get('schritt_prozent')) is not None and _num(pv['schritt_prozent']) > 0
              and _pos_int(pv.get('intervall_minuten'))
              and _num(pv.get('boden_prozent_mw')) is not None and _num(pv['boden_prozent_mw']) >= 0)
        if not ok:
            fehler.append(
                'Achse 10 (preisverfall): bei gebotsrichtung=fallend Pflicht — '
                '{schritt_prozent > 0, intervall_minuten > 0, boden_prozent_mw ≥ 0}.'
            )
    elif pv != 'aus':
        fehler.append(
            'Achse 10 (preisverfall): nur bei gebotsrichtung=fallend erlaubt.'
        )

    # ── Achse 11: Zuschlagspreis ─────────────────────────────────────────
    zp = cfg.get('zuschlagspreis')
    if zp not in ZUSCHLAGSPREISE:
        fehler.append(
            'Achse 11 (zuschlagspreis): Pflicht — eine von '
            + ', '.join(ZUSCHLAGSPREISE) + '.'
        )
    elif zp == 'zweithoechstes_plus_erhoehung' and cfg.get('gewinnerermittlung') != 'hoechstes_gebot':
        fehler.append(
            'Achse 11 (zuschlagspreis): zweithoechstes_plus_erhoehung ist nur mit '
            'gewinnerermittlung=hoechstes_gebot kombinierbar.'
        )

    # ── Achse 12: Teilnahmebedingungen ───────────────────────────────────
    bedingungen = cfg.setdefault('teilnahmebedingungen', [])
    if not isinstance(bedingungen, list):
        fehler.append('Achse 12 (teilnahmebedingungen): Liste erwartet.')
    else:
        for i, cond in enumerate(bedingungen, start=1):
            if not isinstance(cond, dict) or cond.get('art') not in BEDINGUNGSARTEN:
                fehler.append(
                    f'Achse 12, Bedingung {i}: art muss eine von '
                    + ', '.join(BEDINGUNGSARTEN) + ' sein.'
                )
                continue
            art = cond['art']
            if art in ('max_mw_schnitt', 'mindestkontostand'):
                if _num(cond.get('betrag')) is None or _num(cond['betrag']) <= 0:
                    fehler.append(f'Achse 12, Bedingung {i} ({art}): betrag > 0 fehlt.')
            elif art in ('coins', 'freie_kaderplaetze'):
                if not _pos_int(cond.get('anzahl')):
                    fehler.append(f'Achse 12, Bedingung {i} ({art}): anzahl ≥ 1 fehlt.')
            elif art == 'liga':
                ligen = cond.get('ligen')
                if not (isinstance(ligen, list) and ligen
                        and all(isinstance(x, int) for x in ligen)):
                    fehler.append(
                        f'Achse 12, Bedingung {i} (liga): ligen = nicht-leere Liste von Liga-IDs.'
                    )

    # ── Achse 13: Darstellung (Farbe/Regeltext liegen auf dem Model) ─────
    dar = cfg.get('darstellung')
    if dar is not None and not isinstance(dar, dict):
        fehler.append('Achse 13 (darstellung): Objekt erwartet (z. B. {icon: "…"}).')

    # ── Achse 14: Maximallaufzeit ────────────────────────────────────────
    ml = cfg.setdefault('maximallaufzeit', 'aus')
    if ml != 'aus':
        if not (isinstance(ml, dict) and set(ml) == {'tage'} and _pos_int(ml.get('tage'))):
            fehler.append("Achse 14 (maximallaufzeit): 'aus' oder {tage: N ≥ 1}.")
    if (ende == 'haltezeit' and isinstance(hv, dict) and 'konstant' in hv
            and ml == 'aus'):
        fehler.append(
            'Achse 14 (maximallaufzeit): bei Haltezeit mit konstantem Verlauf '
            'Pflicht — sonst kann die Auktion endlos laufen.'
        )

    # ── Achse 15: Gewinnerermittlung ─────────────────────────────────────
    gw = cfg.get('gewinnerermittlung')
    if gw not in GEWINNERERMITTLUNGEN:
        fehler.append(
            'Achse 15 (gewinnerermittlung): Pflicht — eine von '
            + ', '.join(GEWINNERERMITTLUNGEN) + '.'
        )
    if gw == 'naechstliegend_verborgenes_ziel':
        if sicht not in ('nur_gebotsanzahl', 'nichts'):
            fehler.append(
                'Achse 15: naechstliegend_verborgenes_ziel verlangt sichtbarkeit '
                'nur_gebotsanzahl oder nichts (sonst wäre das Ziel erratbar).'
            )
        if gebote != 'genau_1':
            fehler.append(
                'Achse 15: naechstliegend_verborgenes_ziel verlangt '
                'gebote_pro_manager=genau_1.'
            )
        if richtung != 'verdeckt':
            fehler.append(
                'Achse 15: naechstliegend_verborgenes_ziel verlangt '
                'gebotsrichtung=verdeckt.'
            )
        kor = cfg.get('korridor')
        kor_ok = (isinstance(kor, dict)
                  and set(kor) == {'spanne_min_prozent', 'spanne_max_prozent', 'breite_prozent'}
                  and _num(kor.get('spanne_min_prozent')) is not None
                  and _num(kor['spanne_min_prozent']) > 0
                  and _num(kor.get('spanne_max_prozent')) is not None
                  and _num(kor['spanne_max_prozent']) > _num(kor['spanne_min_prozent'])
                  and _num(kor.get('breite_prozent')) is not None
                  and _num(kor['breite_prozent']) > 0)
        if not kor_ok:
            fehler.append(
                'Korridor: bei naechstliegend_verborgenes_ziel Pflicht — '
                '{spanne_min_prozent, spanne_max_prozent (> min), breite_prozent > 0} '
                '(alles in % vom Marktwert).'
            )
    elif 'korridor' in cfg:
        fehler.append(
            'Korridor: nur bei gewinnerermittlung=naechstliegend_verborgenes_ziel erlaubt.'
        )

    # ── Achse 16: Reservierungsfreigabe ──────────────────────────────────
    rf = cfg.get('reservierungsfreigabe')
    if rf not in RESERVIERUNGSFREIGABEN:
        fehler.append(
            'Achse 16 (reservierungsfreigabe): Pflicht — eine von '
            + ', '.join(RESERVIERUNGSFREIGABEN) + '.'
        )

    # ── Laufzeit (Begleitparameter der Deadline) ─────────────────────────
    laufzeit = cfg.get('laufzeit_minuten')
    if ende == 'deadline':
        if not _pos_int(laufzeit):
            fehler.append(
                'laufzeit_minuten: bei endebedingung=deadline Pflicht (ganze Minuten > 0).'
            )
    elif laufzeit is not None:
        fehler.append('laufzeit_minuten: nur bei endebedingung=deadline erlaubt.')

    # ── Querbezüge Richtung ↔ Ende ↔ Gewinner ↔ Freigabe ────────────────
    if richtung in ('fallend', 'fest'):
        if richtung == 'fallend' and ende not in ('erster_zuschlag', 'preisboden'):
            fehler.append(
                'Querbezug: gebotsrichtung=fallend verlangt endebedingung '
                'erster_zuschlag oder preisboden.'
            )
        if richtung == 'fest' and ende != 'erster_zuschlag':
            fehler.append(
                'Querbezug: gebotsrichtung=fest verlangt endebedingung=erster_zuschlag.'
            )
        if gw is not None and gw != 'erster_zuschlag':
            fehler.append(
                'Querbezug: fallend/fest verlangt gewinnerermittlung=erster_zuschlag.'
            )
        if rf is not None and rf != 'sofortige_buchung':
            fehler.append(
                'Querbezug: fallend/fest verlangt reservierungsfreigabe='
                'sofortige_buchung (Zuschlag bucht sofort, ohne Reservierung).'
            )
    else:
        if ende in ('erster_zuschlag', 'preisboden') and richtung is not None:
            fehler.append(
                'Querbezug: endebedingung erster_zuschlag/preisboden gibt es nur '
                'bei fallend/fest.'
            )
        if gw == 'erster_zuschlag' and richtung is not None:
            fehler.append(
                'Querbezug: gewinnerermittlung=erster_zuschlag gibt es nur bei '
                'fallend/fest.'
            )
        if rf == 'sofortige_buchung' and richtung is not None:
            fehler.append(
                'Querbezug: sofortige_buchung gibt es nur bei fallend/fest.'
            )

    if richtung == 'verdeckt':
        if sicht not in ('nur_gebotsanzahl', 'nichts'):
            fehler.append(
                'Querbezug: verdeckte Gebote verlangen sichtbarkeit '
                'nur_gebotsanzahl oder nichts.'
            )
        if rf == 'bei_ueberbietung':
            fehler.append(
                'Querbezug: bei verdeckten Geboten gibt es keine Überbietung — '
                'reservierungsfreigabe=bei_auktionsende nutzen.'
            )

    if fehler:
        raise ValidationError(fehler)
    return cfg
