"""Preis-, Zeit- und Hitze-Formeln der Show-Auktion (Spec §4, §13).

Alle Preisentscheidungen fallen SERVERSEITIG — das Frontend zeigt nur an.
Für die Holländische Auktion rechnet das JS dieselbe Formel zur Anzeige,
maßgeblich bleibt der Server (Spec §4.3).
"""
import math
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

EIN_EURO = Decimal('1')


def _dec(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _euro(value):
    """Auf ganze Euro runden (Auktions-UX arbeitet in ganzen Euro)."""
    return _dec(value).quantize(EIN_EURO, rounding=ROUND_HALF_UP)


def resolve_start_price(config, market_value):
    """Achse 9 → konkreter Startpreis (None bei 'frei')."""
    sp = config.get('startpreis')
    if sp == 'frei' or sp is None:
        return None
    if isinstance(sp, dict) and 'absolut' in sp:
        return _euro(sp['absolut'])
    if isinstance(sp, dict) and 'prozent_mw' in sp:
        if market_value is None:
            raise ValueError('Startpreis in % vom MW braucht einen Marktwert.')
        return _euro(_dec(market_value) * _dec(sp['prozent_mw']) / 100)
    return None


def min_increment(config, referenz):
    """Achse 8 → Mindesterhöhung bezogen auf das Referenzgebot."""
    erh = config.get('mindesterhoehung', 'keine')
    if erh == 'keine' or not isinstance(erh, dict):
        return Decimal('0')
    referenz = _dec(referenz or 0)
    if set(erh) == {'fix'}:
        return _euro(erh['fix'])
    if set(erh) == {'prozent'}:
        return _euro(referenz * _dec(erh['prozent']) / 100)
    mfp = erh.get('max_fix_prozent')
    if mfp:
        raw = max(_dec(mfp['fix']), referenz * _dec(mfp['prozent']) / 100)
        rundung = _dec(mfp.get('rundung') or 0)
        if rundung > 0:
            raw = (raw / rundung).to_integral_value(rounding=ROUND_CEILING) * rundung
        return _euro(raw)
    return Decimal('0')


def hold_duration_hours(config, bid_count):
    """Achse 5 → Haltezeit-Stunden der aktuellen Stufe.

    Degressiv: Stufe 1 gilt ab Auktionsstart UND nach Gebot 1; ab Gebot 2
    rückt die Treppe weiter, die letzte Stufe bleibt stehen (Spec §4.1).
    """
    hv = config['haltezeit_verlauf']
    if 'konstant' in hv:
        return float(hv['konstant'])
    stufen = hv['degressiv']
    idx = 0 if bid_count <= 1 else min(bid_count - 1, len(stufen) - 1)
    return float(stufen[idx])


def hold_step_number(config, bid_count):
    """Anzeige 'Stufe X/N' — X = benutzte Stufe (1-basiert)."""
    hv = config['haltezeit_verlauf']
    if 'konstant' in hv:
        return 1
    stufen = hv['degressiv']
    idx = 0 if bid_count <= 1 else min(bid_count - 1, len(stufen) - 1)
    return idx + 1


def dutch_step_value(config, market_value):
    """Wertverlust pro Intervall (in €, aus % vom MW)."""
    pv = config['preisverfall']
    return _dec(market_value) * _dec(pv['schritt_prozent']) / 100


def dutch_floor(config, market_value):
    pv = config['preisverfall']
    return _euro(_dec(market_value) * _dec(pv['boden_prozent_mw']) / 100)


def dutch_price(config, start_price, market_value, starts_at, now):
    """Aktueller Preis der fallenden Auktion — floor((jetzt−Start)/Intervall)
    Schritte, nie unter den Boden (Spec §4.3, serverseitig maßgeblich)."""
    pv = config['preisverfall']
    intervall_sek = int(pv['intervall_minuten']) * 60
    vergangene = max(0, int((now - starts_at).total_seconds() // intervall_sek))
    preis = _dec(start_price) - vergangene * dutch_step_value(config, market_value)
    return max(dutch_floor(config, market_value), _euro(preis))


def dutch_steps_to_floor(config, start_price, market_value):
    """Anzahl Intervalle bis zum Erreichen des Bodens."""
    schritt = dutch_step_value(config, market_value)
    diff = _dec(start_price) - dutch_floor(config, market_value)
    if diff <= 0 or schritt <= 0:
        return 0
    return int(math.ceil(float(diff / schritt)))


def heat_score(bid_count, distinct_bidders, last_activity_at, now):
    """Hitzemesser (Spec §13): Menge + Konkurrenz + Frische, Skala 0–100.

    Menge      = min(40, 12·ln(1+gebote))
    Konkurrenz = min(30, bieter·6)
    Frische    = 30 (<10 min) / 20 (<1 h) / 10 (<6 h) / 0
    Schwellen: ≥80 Glutheiß · ≥55 Hitzig · ≥30 Es köchelt · sonst Ruhig.
    """
    menge = min(40.0, 12.0 * math.log(1 + max(0, bid_count)))
    konkurrenz = min(30.0, max(0, distinct_bidders) * 6.0)
    frische = 0.0
    if last_activity_at is not None:
        minuten = (now - last_activity_at).total_seconds() / 60.0
        if minuten < 10:
            frische = 30.0
        elif minuten < 60:
            frische = 20.0
        elif minuten < 360:
            frische = 10.0
    score = round(menge + konkurrenz + frische)
    if score >= 80:
        label = 'Glutheiß'
    elif score >= 55:
        label = 'Hitzig'
    elif score >= 30:
        label = 'Es köchelt'
    else:
        label = 'Ruhig'
    return score, label
