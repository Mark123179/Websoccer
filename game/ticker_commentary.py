"""
Deterministischer Live-Ticker-Kommentar im deutschen Radio-Reportage-Stil.

Aufruf: build_ticker_text(evt_type, *, minute, player, …)
Rückgabe: ein einzelner String, deterministisch aus Seed gewählt.

Seed-Formel: hash(evt_type | minute | player | in_name | assister)
→ dasselbe gespeicherte Spiel zeigt bei jedem Reload dieselben Texte.
"""
from __future__ import annotations


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _pick(pool: list[str], seed: int) -> str:
    return pool[abs(seed) % len(pool)]


def _seed(*parts) -> int:
    return abs(hash('|'.join(str(p) for p in parts)))


# ── Tor-Texte ────────────────────────────────────────────────────────────────

_GOAL_ASSIST_ACTIONS = [
    "spielt einen messerscharfen Steckpass in die Tiefe —",
    "legt mit einem direkten Kontakt auf —",
    "bringt eine flache Hereingabe von der rechten Seite —",
    "zieht auf der linken Seite durch und legt quer —",
    "behauptet den Ball gegen zwei Gegenspieler und steckt durch —",
    "schlägt eine präzise Flanke auf den zweiten Pfosten —",
    "kombiniert kurz mit dem Außenstürmer und spielt den Einlaufenden an —",
    "zieht in die Mitte und spielt im richtigen Moment auf —",
    "hat das Auge für den besser postierten Mitspieler —",
    "erkämpft sich den Ball im Mittelfeld und schaltet sofort um —",
    "nimmt einen langen Ball mit der Brust ab und legt direkt für —",
    "chippt den Ball elegant hinter die letzte Abwehrlinie auf —",
]

_GOAL_ASSIST_FINISHES = [
    "{p} hat das leere Tor vor sich und schiebt überlegt ein.",
    "{p} kommt aus dem Lauf und verwertet mit links.",
    "{p} lässt dem Torwart keine Reaktionszeit und trifft flach ins kurze Eck.",
    "{p} nimmt den Ball mit einem Kontakt und zieht sofort ab — drin.",
    "{p} steigt am höchsten und drückt den Ball mit dem Kopf ins Netz.",
    "{p} trifft aus kurzer Distanz ins linke untere Eck.",
    "{p} schlenzt den Ball ins lange Eck — präzise und unhaltbar.",
    "{p} legt sich den Ball mit der Hacke zurecht und vollendet.",
    "{p} bleibt vor dem Torwart eiskalt und schiebt ins rechte Eck.",
    "{p} dreht sich schnell und zieht volley ab — kein Halten.",
]

_GOAL_SOLO_INTROS = [
    "{p} setzt sich über die Außenbahn durch und zieht dann wuchtig ins kurze Eck.",
    "{p} erkämpft sich den Ball im Mittelfeld, schüttelt einen Gegner ab und trifft aus 16 Metern.",
    "{p} nimmt einen Abpraller direkt und lässt dem Keeper keine Chance.",
    "{p} dreht sich am Strafraum um seinen Bewacher und zieht mit links ab — der Ball schlägt unhaltbar ein.",
    "{p} schaltet nach einem Fehlpass des Gegners blitzschnell um und schiebt kaltblütig ein.",
    "{p} kommt aus dem Nichts, übersprintet seinen Bewacher und trifft wuchtig ins Netz.",
    "{p} bekommt den Ball nach einem Eckball-Abpraller, dreht sich und schließt ab — drin.",
    "{p} kombiniert sich im Strafraum frei, nimmt mit rechts an und schiebt mit links ein.",
    "{p} trifft nach einer Standardsituation mit einem direkt angeschlossenen Abschluss.",
    "{p} nimmt einen langen Ball an der Strafraumgrenze mit der Brust ab, lässt den Gegner aussteigen und vollendet.",
    "{p} scheitert zunächst am Torwart, trifft aber im Nachschuss.",
    "{p} bekommt Raum, weil die Abwehr zu spät rückt, und lässt sich diese Einladung nicht entgehen.",
]

_SCORE_PHRASES = [
    "Tor! {score}.",
    "{score} — was ein Treffer!",
    "Das Netz zappelt — {score}.",
    "{score}!",
    "Der Ball ist drin — {score}!",
]


def _goal_with_assist(p: str, a: str, score: str, seed: int) -> str:
    action  = _pick(_GOAL_ASSIST_ACTIONS,  seed)
    finish  = _pick(_GOAL_ASSIST_FINISHES, seed + 7)
    phrase  = _pick(_SCORE_PHRASES,        seed + 13)
    finish  = finish.format(p=p)
    phrase  = phrase.format(score=score)
    return f"{a} {action} {finish} {phrase}"


def _goal_no_assist(p: str, score: str, seed: int) -> str:
    intro  = _pick(_GOAL_SOLO_INTROS, seed)
    phrase = _pick(_SCORE_PHRASES,    seed + 5)
    intro  = intro.format(p=p)
    phrase = phrase.format(score=score)
    return f"{intro} {phrase}"


# ── Schuss-Texte ─────────────────────────────────────────────────────────────

_SHOT_TEXTS = [
    "{p} zieht aus rund 18 Metern ab — der Ball fliegt knapp über die Latte.",
    "{p} kommt nach einem schnellen Dribbling zum Abschluss, scheitert aber am glänzend reagierenden Torwart.",
    "{p} versucht es mit einem platzierten Schuss ins kurze Eck — der Keeper ist zur Stelle.",
    "{p} zieht aus der zweiten Reihe ab, der Schuss geht jedoch deutlich am langen Pfosten vorbei.",
    "{p} dreht sich im Strafraum und zieht sofort ab — knapp am Pfosten vorbei. Das wäre das Tor gewesen.",
    "{p} lässt den Ball klatschen und volley drauf — der Schuss wird im letzten Moment geblockt.",
    "{p} fasst sich ein Herz und schießt aus 22 Metern, trifft den Ball aber nicht sauber. Kein Problem für den Torwart.",
    "{p} kommt in die Schusssituation, verzieht aber deutlich — kein Torschuss im eigentlichen Sinne.",
    "{p} köpft nach einer Flanke aufs Tor — der Schlussmann faustet sicher.",
    "{p} versucht es mit einem Schlenzer aus spitzem Winkel, der Torwart lässt sich davon jedoch nicht überraschen.",
    "{p} zieht nach einem Sololauf aus kurzer Distanz ab — der Keeper macht sich breit und lenkt zur Ecke.",
    "{p} trifft den Ball volley aus der Luft, setzt ihn aber Zentimeter zu hoch an.",
    "{p} läuft in den Strafraum und schießt — die Abwehr wirft sich dazwischen und lenkt ins Aus.",
    "{p} testet den Torwart mit einem Fernschuss — der reagiert mit einer Glanzparade.",
    "{p} hat freie Schussbahn, trifft den Ball aber mit der Außenseite und schickt ihn am Tor vorbei.",
]


# ── Ecken-Texte ──────────────────────────────────────────────────────────────

_CORNER_TEXTS = [
    "{p} tritt die Ecke an und bringt den Ball mit viel Schnitt an den zweiten Pfosten — die Abwehr klärt.",
    "Eckstoß. {p} schlägt den Ball gefährlich in den Strafraum, doch ein Verteidiger ist zur Stelle.",
    "{p} verzieht die Ecke direkt ins Aus — kein Abnehmer.",
    "Kurz gespielter Eckball von {p}. Der Empfänger wird aber sofort unter Druck gesetzt.",
    "{p} schlägt die Ecke direkt auf den ersten Pfosten, wo der Torwart sicher zugreift.",
    "{p} hebt den Ball gefährlich in den Rückraum — niemand kommt entscheidend ran.",
    "Ecke für das angreifende Team. {p} übernimmt — sein Versuch landet in der Mauer.",
    "{p} spielt die Ecke kurz ab, spielt sich frei und flankt dann flach herein — geblockt.",
    "Eine weitere Standardsituation. {p} bringt die Ecke herein, doch der Kopfball des angesprungenen Spielers geht über das Tor.",
    "{p} zieht die Ecke mit Effet Richtung kurzer Pfosten — dort klärt die Abwehr in letzter Sekunde.",
]


# ── Foul-Texte ───────────────────────────────────────────────────────────────

_FOUL_TEXTS = [
    "{p} wird von hinten gelaufen und geht zu Boden — der Schiedsrichter pfeift sofort ab.",
    "Taktisches Foul im Mittelfeld — {p} kommt zu spät und unterbricht einen vielversprechenden Konter.",
    "Pfiff! {p} wird beim Durchstarten im Rücken angegangen. Freistoß.",
    "{p} und ein Gegenspieler suchen denselben Ball — es gibt Körperkontakt. Der Schiedsrichter entscheidet auf Freistoß.",
    "Hartes Einsteigen gegen {p}. Der Schiedsrichter lässt die Karte zunächst stecken, ermahnt aber den Verursacher.",
    "{p} klagt über einen Ellbogenstoß — nach kurzer Diskussion gibt es Freistoß.",
    "Handspiel im Mittelfeld. Freistoß. {p} hat die Möglichkeit, das Spiel neu zu strukturieren.",
    "{p} wird mit einem Gripsen am Trikot gestoppt. Klares Foul — Freistoß in einer aussichtsreichen Position.",
    "Der Gegner kommt zwei Schritte zu spät und trifft {p} am Knöchel. Freistoß — die Behandlung dauert einen Moment.",
    "{p} macht einen Schritt zurück, trifft dabei aber den Gegenspieler. Freistoß für die andere Seite.",
]


# ── Karten-Texte ─────────────────────────────────────────────────────────────

_CARD_YELLOW = [
    "{p} sieht die Gelbe Karte — wohl zu laut protestiert nach der Entscheidung des Schiedsrichters.",
    "Gelb für {p}. Das Foul war eindeutig, der Schiedsrichter zieht die Karte.",
    "{p} kommt einen Schritt zu spät und zieht sich die Verwarnung zu. Das war die erste Gelbe.",
    "Der Schiedsrichter ermahnt {p} und zeigt dann Gelb — damit ist eine weitere Unsportlichkeit teuer bezahlt.",
    "{p} protestiert nach einer Abseits-Entscheidung zu energisch und sieht folgerichtig Gelb.",
    "Ungestümes Einsteigen von {p} — der Schiedsrichter pfeift und greift zur Karte.",
    "Gelbe Karte für {p}. Bei einem weiteren Vergehen wäre das Spiel für ihn beendet.",
    "{p} hält den Gegner am Arm fest und kommt damit nicht durch — der Schiedsrichter zeigt Gelb.",
]

_CARD_YELLOW_RED = [
    "Gelb-Rot für {p}! Das zweite Vergehen innerhalb kurzer Zeit — jetzt muss er früher vom Platz.",
    "{p} sieht die Gelb-Rote Karte. Das war ein Foul zu viel — die Mannschaft muss nun in Unterzahl ran.",
    "Zweite Gelbe für {p} — damit ist die Partie für ihn vorzeitig beendet. Die Bank ist fassungslos.",
    "Der Schiedsrichter zeigt {p} zunächst die zweite Gelbe, dann direkt die Rote. Unterzahl!",
    "{p} macht ein taktisches Foul, hat dabei aber nicht bedacht, dass er schon verwahnt war. Gelb-Rot — Ende.",
]

_CARD_RED = [
    "Platzverweis! {p} sieht nach einem rüden Einsteigen die Rote Karte direkt.",
    "Rote Karte für {p}! Das war eine klare Notbremse — der Schiedsrichter zieht sofort die Karte.",
    "{p} trifft den Gegner mit gestrecktem Bein — der Schiedsrichter überlegt keine Sekunde und zeigt Rot.",
    "Tätlichkeit von {p} — der Schiedsrichter greift sofort in die Tasche. Rote Karte, Unterzahl.",
    "{p} fliegt vom Platz. Das war ein Einsteigen, das keine andere Konsequenz haben durfte.",
]


# ── Wechsel-Texte ────────────────────────────────────────────────────────────

_SUB_HP = [
    "Wechsel: {i} kommt für {o}. Der Trainer reagiert auf die Spielentwicklung.",
    "{o} verlässt das Feld — {i} betritt es. Taktische Maßnahme.",
    "Einwechslung: {i} ersetzt {o} und soll frischen Schwung bringen.",
    "{o} hat seinen Teil geleistet, jetzt ist {i} an der Reihe.",
    "Der Trainer schickt {i} auf den Platz. {o} darf runter.",
    "{i} kommt für {o} — der Coach will mit dem Wechsel neue Impulse setzen.",
    "{o} verlässt unter Applaus den Platz, {i} übernimmt seine Aufgaben.",
    "Spielerwechsel: Für {o} kommt {i} neu in die Partie.",
]

_SUB_FP = [
    "Wechsel: {i} kommt für {o} — und übernimmt dabei eine für ihn ungewohnte Position ({slot}).",
    "Der Trainer stellt um: {i} ersetzt {o} und spielt nun auf {slot}. Eine taktische Notlösung.",
    "Einwechslung: {i} für {o}. Auf Position {slot} agiert {i} nun außerhalb seiner Stammposition.",
]

_SUB_NP = [
    "Wechsel: {i} kommt für {o} auf der Nebenposition {slot}.",
    "{i} ersetzt {o} und übernimmt auf {slot} — nicht seine Lieblingsposition, aber er kennt sie.",
    "Einwechslung: {i} für {o}, diesmal auf Nebenposition {slot}.",
]

_SUB_INJURY = [
    "{i} muss als Notlösung ran — {o} kann nach der Verletzung nicht weitermachen.",
    "Verletzungswechsel: {o} signalisiert, dass es nicht geht. {i} kommt.",
    "{o} humpelt vom Platz, {i} ist die Antwort des Trainerteams.",
    "Behandlungspause für {o} — er kann nicht weiterspielen. {i} kommt neu.",
    "{o} wird gestützt vom Feld geführt. {i} bereitet sich hastig vor und betritt jetzt den Platz.",
]


# ── Verletzungs-Texte ────────────────────────────────────────────────────────

_INJURY_TEXTS = [
    "{p} bleibt nach einem Zweikampf am Boden liegen und muss behandelt werden. Nach kurzer Unterbrechung signalisiert er, dass es weitergeht.",
    "{p} greift sich nach einem Zusammenprall ans Bein. Die medizinische Abteilung kommt aufs Feld — nach einigen Momenten steht er aber wieder.",
    "Behandlungspause für {p}. Er hat sich den Knöchel verdreht, kann aber nach der Behandlung weitermachen.",
    "{p} klagt über Schmerzen an der Schulter, nachdem er in einem Kopfballduell den Ellbogen abbekommen hat.",
    "{p} humpelt kurz nach einem Zweikampf, schüttelt den Schmerz aber weg. Keine Auswechslung notwendig.",
    "{p} liegt nach einem harten Einsatz am Boden. Der Sanitäter kommt sofort — nach einer kurzen Pause steht er wieder.",
]

_INJURY_SUB_TEXTS = [
    "{p} kann nach der Verletzung nicht weitermachen. Die medizinische Abteilung signalisiert sofort, dass ein Wechsel nötig ist.",
    "{p} bleibt verletzt am Boden. Es dauert nicht lange, bis klar ist: Er muss raus.",
    "Schlechte Nachrichten — {p} verdreht sich das Knie und muss ausgewechselt werden.",
    "{p} greift sich nach einem Zusammenprall an den Oberschenkel und winkt ab. Er kann nicht weiterspielen.",
    "{p} versucht es noch, aber nach wenigen Schritten merkt auch er selbst, dass ein Weiterspielen unmöglich ist.",
]


# ── Spielfluss-Texte ─────────────────────────────────────────────────────────
# Diese nutzen {h} = Heimteam, {a} = Auswärtsteam, {p} = Spieler (optional)

_FLOW_WITH_PLAYER = [
    "{p} fordert den Ball immer wieder tief in der eigenen Hälfte und eröffnet das Spiel mit präzisen Pässen.",
    "{p} behauptet den Ball gegen zwei Gegenspieler und befreit sich mit einem Haken.",
    "{p} sucht immer wieder das Eins-gegen-Eins auf der Außenbahn — heute kommt er gut durch.",
    "{p} verliert den Ball zwar zunächst, erkämpft ihn aber sofort zurück. Starkes Anlaufen.",
    "{p} versucht einen Steilpass in die Tiefe, aber der Abwehrchef antizipiert und klärt souverän.",
    "{p} versucht es mit einem Chipball auf den einlaufenden Stürmer — der Ball landet aber beim Torwart.",
    "{p} verwaltet das Tempo im Mittelfeld und gibt dem Spiel Struktur.",
    "{p} lässt den Ball klatschen und sucht gleich den nächsten Anspielpartner.",
    "{p} setzt sich auf der rechten Seite durch und schlägt dann die Flanke — kein Abnehmer.",
    "{p} spielt einen scharfen Pass in die Tiefe — die Abwehr des Gegners ist aber zur Stelle.",
]

_FLOW_TEAM = [
    "{h} kombiniert sich flüssig durch die eigenen Reihen, findet gegen das kompakte {a}-Defensivblock aber noch keine Lücke.",
    "{a} übt intensives Pressing aus und gewinnt den Ball im Mittelfeld zurück.",
    "{h} dominiert derzeit den Spielaufbau und lässt den Ball geduldig laufen.",
    "Das Spiel wird hektischer — beide Mannschaften suchen schnelle Pässe nach vorne.",
    "{a} zieht sich in der eigenen Hälfte zurück und lauert auf Konter.",
    "Ruhigere Phase — beide Teams abtasten, kein Risiko.",
    "{h} erhöht das Tempo und zieht das Angriffsspiel auf die Flügel.",
    "{a} gewinnt zunehmend Kontrolle im Mittelfeld.",
    "Tempowechsel von {h} bringt die Defensive des Gegners kurz in Not.",
    "{a} sucht die Außenbahn häufig und schlägt eine Flanke nach der anderen herein.",
    "Starkes Gegenpressing von {h} — der Ball kommt kaum über die Mittellinie.",
    "Eine längere Phase ohne klare Torchance auf beiden Seiten — die Partie läuft sich fest.",
    "Freistoß wird schnell hereingebracht, {h} schaltet schnell um. Vielversprechend.",
    "{a} hat eine Fehlpassserie — das Spielmaterial des Gegners, den es zu nutzen gilt.",
    "{h} lässt den Ball durch die eigenen Reihen laufen und sucht eine Lücke.",
    "Beide Mannschaften kämpfen intensiv im Mittelfeld — bisher ein ausgeglichenes Spiel.",
    "{a} kombiniert sich auf engem Raum durch, wird aber dann von der kompakten Defensive gestoppt.",
    "Nach dem letzten Treffer hat {h} das Spiel beruhigt und verwaltet den Vorsprung.",
    "{a} erhöht den Druck und kommt immer mehr in die Partie.",
    "{h} spielt jetzt mit mehr Risiko nach vorne — der Anschluss muss her.",
    "Das Pressing von {a} zwingt {h} zu langen Bällen, die aber kaum ankommen.",
]


# ── Hauptfunktion ────────────────────────────────────────────────────────────

def build_ticker_text(
    evt_type: str,
    *,
    minute: int = 0,
    player: str = '',
    assister: str = '',
    card_type: str = '',
    score_h: int = 0,
    score_a: int = 0,
    days: int = 0,
    in_name: str = '',
    out_name: str = '',
    target_slot: str = '',
    position_relation: str = '',
    team_name: str = '',
    opp_name: str = '',
    is_injury_sub: bool = False,
) -> str:
    base = _seed(evt_type, minute, player or in_name, assister)
    p = player or ''
    a = assister or ''
    score = f'{score_h}:{score_a}'

    if evt_type == 'goal':
        if a:
            return _goal_with_assist(p, a, score, base)
        else:
            return _goal_no_assist(p, score, base)

    elif evt_type == 'shot':
        if p:
            return _pick(_SHOT_TEXTS, base).format(p=p)
        return "Schussversuch — der Torwart ist auf dem Posten."

    elif evt_type == 'corner':
        if p:
            return _pick(_CORNER_TEXTS, base).format(p=p)
        return "Eckstoß — die Abwehr klärt."

    elif evt_type == 'foul':
        if p:
            return _pick(_FOUL_TEXTS, base).format(p=p)
        return "Pfiff — Freistoß."

    elif evt_type == 'card':
        if card_type == 'yellow_red':
            return _pick(_CARD_YELLOW_RED, base).format(p=p)
        elif card_type == 'red':
            return _pick(_CARD_RED, base).format(p=p)
        else:
            return _pick(_CARD_YELLOW, base).format(p=p)

    elif evt_type == 'sub':
        i = in_name or ''
        o = out_name or ''
        slot = target_slot or ''
        if is_injury_sub:
            return _pick(_SUB_INJURY, base).format(i=i, o=o)
        elif position_relation == 'FP' and slot:
            return _pick(_SUB_FP, base).format(i=i, o=o, slot=slot)
        elif position_relation == 'NP' and slot:
            return _pick(_SUB_NP, base).format(i=i, o=o, slot=slot)
        else:
            return _pick(_SUB_HP, base).format(i=i, o=o)

    elif evt_type == 'injury':
        if days and days > 7:
            return _pick(_INJURY_SUB_TEXTS, base).format(p=p)
        return _pick(_INJURY_TEXTS, base).format(p=p)

    elif evt_type == 'flow':
        # flow-Texte werden direkt in _generate_narrative_events gesetzt
        return player or f'Spielunterbrechung in Minute {minute}.'

    return f'Spielunterbrechung in Minute {minute}.'


def build_flow_text(
    minute: int,
    seed: int,
    h_name: str = '',
    a_name: str = '',
    h_players: list[str] | None = None,
    a_players: list[str] | None = None,
    team_side: str = 'home',
) -> str:
    """Wählt deterministisch einen Spielfluss-Kommentar.

    Nutzt Spielernamen wenn verfügbar, sonst nur Teamnamen.
    """
    h = h_name or 'Heim'
    a = a_name or 'Gast'
    all_players = (h_players or []) + (a_players or [])

    if all_players and (seed % 3 == 0):
        p = all_players[seed % len(all_players)]
        return _pick(_FLOW_WITH_PLAYER, seed).format(p=p, h=h, a=a)
    else:
        text = _pick(_FLOW_TEAM, seed)
        return text.format(h=h, a=a)
