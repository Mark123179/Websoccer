"""
Deterministischer Live-Ticker-Kommentar im deutschen Radio-Reportage-Stil.

Aufruf: build_ticker_text(evt_type, *, minute, player, …, match_seed, event_index)
Rückgabe: ein einzelner String, deterministisch aus Seed gewählt.

Seed: stable_seed() via SHA-256 — prozessübergreifend stabil (kein PYTHONHASHSEED).
Anti-Repetition: _shuffled_pick() erzeugt pro Spiel + Pool eine stabile Permutation;
  event_index bestimmt die Position darin → keine Wiederholung bis Pool erschöpft.

Platzhalter-Schema:
  {p}  = Hauptspieler (Torschütze, Kartenempfänger, …)
  {a}  = zweiter Spieler (Vorlagengeber, Zweikampfgegner, …)
  {h}  = angreifendes/Heim-Team
  {o}  = Gegner/Auswärts-Team
  {i}  = Eingewechselter (Wechsel-Texte)
  {o}  = Ausgewechselter (Wechsel-Texte — Kontext macht Verwendung eindeutig)
"""
from __future__ import annotations
import random as _random

from .random_utils import stable_seed  # noqa: F401 — re-exportiert für Abwärtskompatibilität


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _shuffled_pick(pool: list[str], match_seed: int, pool_key: str, event_index: int) -> str:
    """Wählt aus `pool` nach einer spielspezifischen Permutation.

    Garantiert: innerhalb eines Spiels wird jede Variante maximal
    einmal verwendet bevor Wiederholungen auftreten.
    """
    r = _random.Random(stable_seed(match_seed, pool_key))
    indices = list(range(len(pool)))
    r.shuffle(indices)
    return pool[indices[event_index % len(pool)]]


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
    # OWS-Ergänzungen
    "legt gekonnt ab —",
    "spielt einen genauen Steilpass —",
    "schlägt eine scharfe Flanke auf —",
    "setzt mit einem Kurzpass in Szene —",
    "spielt den Ball direkt in den Lauf von —",
    "legt mit der Hacke auf —",
]

# Torhüter als Vorlagengeber — lange Abschläge, schnelle Abwürfe, Verteilung
_GOAL_GK_ASSIST_ACTIONS = [
    "schlägt einen langen Abschlag weit nach vorne —",
    "wirft den Ball blitzschnell ab und leitet den Konter ein —",
    "spielt einen präzisen Abschlag hinter die Abwehrkette —",
    "verteilt den Ball mit einem langen Tritt ins Angriffsdrittel —",
    "hält kurz und schlägt dann einen weiten Ball auf —",
    "startet den Konter mit einem schnellen Abwurf auf —",
    "schmeißt den Ball flach ab und findet —",
    "spielt den Torabstoß direkt auf den startenden —",
    "schlägt den Ball aus der Hand genau in den Lauf von —",
    "antizipiert den Gegenpressing und spielt sofort lang auf —",
    "rollt den Ball schnell aus — perfekte Einladung für —",
    "tritt den Ball weit nach vorne — und da ist —",
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
    # OWS-Ergänzungen
    "{p} braucht nur noch einzuschieben.",
    "{p} nimmt die Flanke direkt ab — der Torhüter hat keine Chance.",
    "{p} wird in Szene gesetzt und verwandelt eiskalt.",
    "{p} donnert den Ball in einer Bewegung ins Netz.",
    "{p} muss nur noch den Fuß hinhalten — drin!",
]

_GOAL_GK_SOLO_INTROS = [
    "{p} wagt es aus der Distanz — ein Traumtor des Torhüters! Der Ball schlägt unhaltbar ein.",
    "Der Torhüter {p} nimmt Anlauf und drischt den Ball aus gut 50 Metern ins Netz — unglaublich!",
    "{p} sieht den gegnerischen Keeper weit vor dem Tor stehen und lupft ihn eiskalt — Tor!",
    "Beim Eckstoß rückt {p} auf — und köpft tatsächlich ein. Das gibt es nicht!",
    "Ein langer Freistoß landet bei {p}, der aus dem Nichts zum Abschluss kommt — drin!",
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
    # OWS-Ergänzungen
    "{p} schießt — TOR! Wunderschön gemacht.",
    "Knallhart setzt {p} den Ball unter die Latte ins Tor.",
    "Nach einer Ball-Stafette macht {p} das Tor.",
    "{p} traut sich was, er zieht aus 26 Metern ab — der Ball schlägt unhaltbar ein.",
    "{p} stiehlt sich an der Strafraumgrenze eiskalt den Ball und verwandelt nach einer herrlichen Drehung ins untere linke Eck.",
    "{p} nimmt sich einfach den Mut und drescht das Ding unhaltbar mit voller Wucht in die Mitte des Tores.",
    "Katastrophaler Fehler des Gegners, der sofort bestraft wird — {p} mit einem klasse Solo, das durch ein TOR belohnt wird.",
    "{p} schafft es seinen Bewacher auszudribbeln und braucht den Ball nur noch einzuschieben. TOR!",
    "Da wurde der Gegner gnadenlos ausgekontert! {p} schlägt eiskalt zu und überrascht den Torwart mit einem Lupfer.",
    "{p} dribbelt sich durch die gegnerische Abwehr und probiert es einfach — drin!",
    "Ein Stellungsfehler in der Abwehr — {p} nutzt den Schnitzer und schiebt den Ball ins Gehäuse.",
    "Nach einer guten Kombination steckt er den Ball durch, und {p} verwandelt alleine vorm Keeper sicher.",
    "{p} kommt zum Kopfball — und da flattert der Ball im Netz!",
    "Mit dem Heber konnte {p} sein Torkonto bereichern — tolle Szene!",
]

_SCORE_PHRASES = [
    "Tor! {score}.",
    "{score} — was ein Treffer!",
    "Das Netz zappelt — {score}.",
    "{score}!",
    "Der Ball ist drin — {score}!",
]


_GK_POSITIONS = frozenset({'TW', 'GK', 'GOALKEEPER'})


def _goal_with_assist(p: str, a: str, score: str, match_seed: int, event_index: int,
                      *, gk_assist: bool = False) -> str:
    if gk_assist:
        action = _shuffled_pick(_GOAL_GK_ASSIST_ACTIONS, match_seed, 'goal_gk_action', event_index)
    else:
        action = _shuffled_pick(_GOAL_ASSIST_ACTIONS, match_seed, 'goal_action', event_index)
    finish = _shuffled_pick(_GOAL_ASSIST_FINISHES, match_seed, 'goal_finish',  event_index)
    phrase = _shuffled_pick(_SCORE_PHRASES,        match_seed, 'score_phrase', event_index)
    return f"{a} {action} {finish.format(p=p)} {phrase.format(score=score)}"


def _goal_no_assist(p: str, score: str, match_seed: int, event_index: int,
                    *, gk_scorer: bool = False) -> str:
    if gk_scorer:
        intro = _shuffled_pick(_GOAL_GK_SOLO_INTROS, match_seed, 'goal_gk_solo', event_index)
    else:
        intro = _shuffled_pick(_GOAL_SOLO_INTROS, match_seed, 'goal_solo', event_index)
    phrase = _shuffled_pick(_SCORE_PHRASES, match_seed, 'score_phrase', event_index)
    return f"{intro.format(p=p)} {phrase.format(score=score)}"


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
    # OWS Torschuss_daneben
    "{p} hat freie Bahn und schießt — weit über das Tor.",
    "{p} schießt — daneben.",
    "Kopfball von {p} — daneben.",
    "{p} haut mit aller Kraft auf den Ball — Abschlag.",
    "{p} schießt in die Wolken.",
    "Knapp vorbei, weil {p} zu genau gezielt hat.",
    "{p} versucht es mit einem Fallrückzieher — aber doch daneben.",
    "{p} versucht es mit einem Volleyschuss — knapp drüber.",
    "Wie Slalomstangen umkurvt {p} seine Gegenspieler und probiert es mit einem Schlenzer — knapp drüber.",
    # OWS Torschuss_auf_Tor
    "{p} schießt — Glanzparade des Torwarts!",
    "{p} schießt auf das Tor — aber der Torwart macht einen Hechtsprung und hat den Ball.",
    "{p} hat freie Bahn und schießt — aber der Torwart dreht den Ball gerade noch so um den Pfosten.",
    "{p} kommt zum Kopfball — ganz knapp daneben.",
    "Ein Heberversuch von {p}, doch der Torhüter bekommt noch den Ball.",
    "Was für ein Lattenknaller! So bleibt der Spielstand unverändert.",
    "Unterkante Latte — und doch nicht im Tor. Glück für die Verteidigung.",
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
    # OWS-Ergänzungen
    "{p} schlägt die Ecke zentral in den Strafraum — weit und breit kein Mitspieler.",
    "Die Flanke von {p} ist etwas zu hoch, um noch irgendwie erreicht zu werden.",
    "Die Flanke von {p} segelt über den Strafraum und geht ins Seitenaus.",
    "Kurze Ecke von {p}, doch der Gegner hat den Braten gerochen und unterbindet den Angriff.",
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
    # OWS-Ergänzungen
    "{p} bekommt nach einem Foul die gelbe Karte.",
    "{p} haut seinen Gegenspieler um und bekommt dafür die gelbe Karte.",
    "{p} mit einem weiteren Foul — diesmal hagelt es die Gelbe Karte.",
    "Ein verstecktes Foul bringt {p} nun die gelbe Karte ein.",
    "{p} wollte die Hand nicht vom Trikot des Gegners lassen und sieht Gelb.",
    "Für diese Schauspieleinlage bekommt {p} zurecht die Gelbe.",
    "{p} glaubt es nicht — er bekommt die gelbe Karte zu Unrecht.",
    "{p} drischt den Ball einfach weg, obwohl der Schiedsrichter das Spiel schon unterbrochen hatte.",
    "Konsequenterweise bekommt {p} Gelb für diese Unsportlichkeit.",
    "{p} zettelt einen Streit an und kassiert folglich die gelbe Karte.",
    "{p} ist nicht einverstanden mit der Auslegung und bekommt fürs Meckern die gelbe Karte.",
    "Der Gegenspieler krümmt sich vor Schmerzen am Boden, und {p} hat großes Glück, dass er nur gelb bekommen hat.",
    "{p} hat das Timing für die Grätsche kräftig verpasst und knüppelt seinen Gegenspieler um. Gelb.",
    "Dieses taktische Foul von {p} zieht nun doch die Karte nach sich.",
    "Für dieses klare Zeitspiel erhält {p} die gelbe Karte.",
]

_CARD_YELLOW_RED = [
    "Gelb-Rot für {p}! Das zweite Vergehen innerhalb kurzer Zeit — jetzt muss er früher vom Platz.",
    "{p} sieht die Gelb-Rote Karte. Das war ein Foul zu viel — die Mannschaft muss nun in Unterzahl ran.",
    "Zweite Gelbe für {p} — damit ist die Partie für ihn vorzeitig beendet. Die Bank ist fassungslos.",
    "Der Schiedsrichter zeigt {p} zunächst die zweite Gelbe, dann direkt die Rote. Unterzahl!",
    "{p} macht ein taktisches Foul, hat dabei aber nicht bedacht, dass er schon verwahnt war. Gelb-Rot — Ende.",
    # OWS-Ergänzungen
    "{p} sieht die Gelb-Rote Karte und muss vom Platz.",
    "{p} haut seinen Gegenspieler um und bekommt dafür die Gelb-Rote Karte.",
    "Das Foul musste nicht sein — dafür kassiert {p} nun Gelb/Rot.",
    "{p} hatte ein taktisches Foul zu viel und muss nach der zweiten groben Aktion vom Platz.",
    "Jetzt reicht es dem Schiedsrichter — {p} sieht nun Gelb/Rot.",
    "Eine wirklich dumme Aktion: {p} springt von hinten in die Beine seines Gegners. Zweite Gelbe — Ende.",
    "Kurz vor dem Strafraum verschätzt sich {p} bei einem aufspringenden Ball und hält den Stürmer. Als letzter Mann kassiert er Gelb-Rot.",
]

_CARD_RED = [
    "Platzverweis! {p} sieht nach einem rüden Einsteigen die Rote Karte direkt.",
    "Rote Karte für {p}! Das war eine klare Notbremse — der Schiedsrichter zieht sofort die Karte.",
    "{p} trifft den Gegner mit gestrecktem Bein — der Schiedsrichter überlegt keine Sekunde und zeigt Rot.",
    "Tätlichkeit von {p} — der Schiedsrichter greift sofort in die Tasche. Rote Karte, Unterzahl.",
    "{p} fliegt vom Platz. Das war ein Einsteigen, das keine andere Konsequenz haben durfte.",
    # OWS-Ergänzungen
    "{p} springt von hinten in die Beine seines Gegenspielers und sieht sofort die Rote Karte.",
    "{p} haut seinen Gegenspieler um und sieht dafür die Rote Karte.",
    "{p} bekommt die Rote Karte wegen Tätlichkeit.",
    "{p} sieht nach einem bösen Foul die Rote Karte und muss vom Platz.",
    "Klare Notbremse! {p} kann den Angreifer nur noch mit unfairen Mitteln stoppen — zur Folge die Rote Karte!",
    "Bei {p} reißen die Nerven durch und er schlägt dem Gegner ins Gesicht. Absolut gerechtfertigte Rote Karte.",
    "{p} springt hoch und trifft seinen Gegenspieler mit dem Ellbogen im Gesicht — der Schiri schickt ihn zum Duschen.",
    "{p} springt seinem Gegenüber von hinten in die Beine — Rote Karte, und das zurecht.",
    "Nach einem Gerangel tritt {p} unsportlich nach und erhält umgehend eine Freikarte für die Dusche.",
    "Laufduell auf der Außenbahn: {p} stoppt den Ball einfach per Hand und kassiert dafür eine klare rote Karte.",
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
    # OWS-Ergänzungen
    "{i} kommt für {o}.",
    "{i} kommt für {o}. Ist {i} vielleicht der Matchwinner?",
    "{i} kommt für {o} und soll den Druck verstärken.",
    "{o} verlässt unter Pfiffen das Feld. Der Trainer hofft, dass {i} seine Sache besser macht.",
    "{o} verlässt den Platz, ohne seinen Trainer abzuklatschen — {i} ersetzt ihn.",
    "{o} hat alles versucht und wird nun von {i} ersetzt.",
    "{i} kommt ins Spiel — ob er Belebung bringen kann? Dafür muss {o} weichen.",
    "Unter Protest verlässt {o} den Platz, dem der eingewechselte {i} weichen muss.",
    "{o} macht kein schlechtes Spiel, muss aber trotzdem für {i} das Feld räumen.",
    "{o} wird mit viel Applaus für seine heutige Leistung von den Fans verabschiedet — {i} will es genauso gut machen.",
    "Damit ist die Partie für {o} beendet — {i} darf nun sein Glück versuchen.",
    "Der Trainer gibt letzte Instruktionen an {i}, der nun für {o} in die Partie kommt.",
    "Wechsel! Für {o} kommt jetzt eine frische Kraft: {i}.",
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

_SUB_GK_RED = [
    "Pflicht-Einwechslung: Der Torwart wurde des Feldes verwiesen — {i} übernimmt das Tor. {o} muss dafür weichen.",
    "Regelkonformer Tausch nach dem Platzverweis des Keepers: {i} ins Tor, {o} vom Platz.",
    "{i} muss das Trikot wechseln — er übernimmt das Tor nach dem Rot für den Keeper. {o} verlässt das Spielfeld.",
    "Erzwungener Wechsel: {i} wird als Ersatztorwart eingewechselt. {o} muss das Feld freimachen.",
    "Nach dem Platzverweis des Torwarts greift der Trainer zur einzigen Option — {i} ins Tor, {o} raus.",
    "{o} muss für {i} den Platz räumen: Pflicht-Einwechslung nach Torhüter-Rot.",
]


# ── Verletzungs-Texte ────────────────────────────────────────────────────────

_INJURY_TEXTS = [
    "{p} bleibt nach einem Zweikampf am Boden liegen und muss behandelt werden. Nach kurzer Unterbrechung signalisiert er, dass es weitergeht.",
    "{p} greift sich nach einem Zusammenprall ans Bein. Die medizinische Abteilung kommt aufs Feld — nach einigen Momenten steht er aber wieder.",
    "Behandlungspause für {p}. Er hat sich den Knöchel verdreht, kann aber nach der Behandlung weitermachen.",
    "{p} klagt über Schmerzen an der Schulter, nachdem er in einem Kopfballduell den Ellbogen abbekommen hat.",
    "{p} humpelt kurz nach einem Zweikampf, schüttelt den Schmerz aber weg. Keine Auswechslung notwendig.",
    "{p} liegt nach einem harten Einsatz am Boden. Der Sanitäter kommt sofort — nach einer kurzen Pause steht er wieder.",
    # OWS-Ergänzungen
    "{p} ist verletzt und muss vom Spielfeld getragen werden.",
    "{p} hat sich verletzt und kann nicht mehr weiterspielen.",
    "Da hat der Gegenspieler voll zugelangt, so dass {p} vom Platz muss.",
    "{p} war schon die ganze Zeit angeschlagen und darf nun vom Platz.",
    "Vorsorglich wird {p} vom Platz genommen.",
    "{p} verfehlt den Ball und knallt mit dem Kopf gegen den Pfosten!",
    "Mitten im Sprint knickt {p} weg — mit schmerzverzerrtem Gesicht humpelt er in die Umkleide.",
    "{p} bekommt einen Ellbogen gegen die Nase und muss blutüberströmt vom Feld.",
    "Nach diesem unglücklichen Tritt in den Rasen ist für {p} die Partie vorzeitig beendet.",
    "Eine Muskelverhärtung im Oberschenkel zwingt {p} zur Aufgabe.",
    "{p} bleibt nach diesem Zweikampf am Boden liegen — nach kurzer Behandlung ist klar, dass er nicht mehr weitermachen kann.",
    "Mit schmerzverzerrtem Gesicht wird {p} mit der Trage vom Platz getragen. Hoffen wir, dass es nichts Schlimmes ist.",
]

_INJURY_SUB_TEXTS = [
    "{p} kann nach der Verletzung nicht weitermachen. Die medizinische Abteilung signalisiert sofort, dass ein Wechsel nötig ist.",
    "{p} bleibt verletzt am Boden. Es dauert nicht lange, bis klar ist: Er muss raus.",
    "Schlechte Nachrichten — {p} verdreht sich das Knie und muss ausgewechselt werden.",
    "{p} greift sich nach einem Zusammenprall an den Oberschenkel und winkt ab. Er kann nicht weiterspielen.",
    "{p} versucht es noch, aber nach wenigen Schritten merkt auch er selbst, dass ein Weiterspielen unmöglich ist.",
    # OWS-Ergänzungen
    "Bittere Pille — {p} setzt zum Volley an, wird dabei aber umgegrätscht und muss vom Platz getragen werden.",
    "Das ist bitter für {p}, der nach einem rüden Foul vom Platz getragen werden muss.",
    "{p} erhält einen Schubser, der zu einem Zusammenprall mit einem Mannschaftskollegen führt — mit blutender Nase wird er vom Platz geführt.",
    "Eine unfaire Attacke am Seitenrand — {p} wird mit übermäßigem Einsatz auf den Fuß getreten, und das Spiel ist für ihn hier zu Ende.",
    "Das sieht nicht gut aus. {p} wird unglücklich getroffen und muss das Spielfeld mit einer Wunde verlassen.",
]


# ── Zweikampf-Texte ──────────────────────────────────────────────────────────

_TACKLE_WIN_TEXTS = [
    "{p} geht auf seinen Gegenspieler zu und gewinnt den Zweikampf!",
    "{p} in einem Zweikampf — gewonnen!",
    "{p} läuft mit dem Ball am Fuß auf seinen Gegenspieler zu und gewinnt den Zweikampf.",
    "{p} nimmt seinem Gegenspieler gekonnt den Ball von den Füßen.",
    "{p} steigt energisch ein und nimmt {a} den Ball von den Füßen.",
    "{a} hatte das Nachsehen, als {p} ihm den Ball weglufte.",
    "{p} ließ {a} einfach stehen.",
    "{p} legt den Ball rechts an {a} vorbei und sprintet links an ihm vorbei. Damit hat {a} überhaupt nicht gerechnet.",
    "{p} tanzt elegant durch das Mittelfeld und entkommt sogar einer Grätsche von {a}.",
    "{p} läuft alleine auf {a} zu und weicht ihm mit einer schönen Pirouette aus.",
    "{p} kämpft sich durch die Reihen und entgleitet irgendwie noch dem Bein von {a}.",
    "Geschickter Ballgewinn von {p} — routiniert spitzelt er {a} den Ball von den Füßen.",
    "Gut aufgepasst von {p}, der im richtigen Moment die Tür zumacht. {a} wäre sonst durchgestartet.",
    "{p} macht das in dieser Szene ganz clever — er läuft seinem Gegner einfach den Ball ab.",
    "{a} setzt zum Tempodribbling an. Doch {p} geht da mit der richtigen Härte rein und gewinnt den Zweikampf.",
    "Mit dieser präzisen Grätsche gegen {a} unterbindet {p} den schnellen Konter.",
    "{p} erobert mit einem beherzten Einsteigen den Ball. Alles fair.",
    "Immer wieder schön zu sehen, wenn {p} den Ball so gekonnt mitnimmt.",
    "{p} darf man nicht aus den Augen lassen — so hat man keine Chance ihn aufzuhalten.",
]

_TACKLE_LOSS_TEXTS = [
    "{p} geht auf {a} zu — und verliert den Zweikampf.",
    "{p} in einem Zweikampf — und verliert ihn.",
    "{p} geht mit dem Ball am Fuß auf seinen Gegenspieler zu und verliert ihn.",
    "{p} sieht seinen Gegenspieler gegenüber und lässt sich den Ball abnehmen.",
    "{p} begibt sich ins Laufduell mit {a}, kann aber nicht vorbeiziehen.",
    "{p} macht einfach gar nichts und verliert den Ball.",
    "{a} spielt Katz und Maus mit {p}.",
    "{p} versucht mit einem Übersteiger an {a} vorbeizukommen, doch er verliert den Ball.",
    "Entweder zu sicher oder zu lustlos — jedenfalls verliert {p} schon wieder den Ball an {a}.",
    "{p} läuft und läuft und scheint {a} gar nicht zu sehen — der Ballbesitz wechselt die Seiten.",
    "Toller Pass aus der Bedrängnis zu {p}. Der bekommt den Ball aber nicht unter Kontrolle und vertändelt ihn gegen {a}.",
    "{p} läuft sich in dieser Situation fest — {a} gewinnt den Zweikampf.",
    "Die schnelle Ballverarbeitung ist nicht seine Stärke. {p} schaut {a} verdutzt hinterher, der den Ball jetzt am Fuß führt.",
    "{p} dribbelt durch zwei Gegenspieler durch, will auch noch an {a} vorbei — aber das geht nicht!",
]


# ── Fehlpass-Texte ───────────────────────────────────────────────────────────

_PASS_FAIL_TEXTS = [
    "Flanke von {p} — in die Wolken!",
    "{p} passt den Ball in die Mitte — genau auf die Füße des Gegners.",
    "{p} passt den Ball steil nach vorne — Abschlag!",
    "Pass von {p} — ins Seitenaus.",
    "Wieder lässt sich {p} unnötig den Ball abnehmen.",
    "{p} macht einen Querpass, der aber nicht ankommt.",
    "{p} versucht mit einem weiten Pass das Spiel zu öffnen — aber der Ball kommt nicht an.",
    "{p} überzeugte mit seinem Passspiel wenig.",
    "{p}'s Direktabnahme hatte nicht die gewünschte Wirkung.",
    "{p}'s Pass klebt am Fuß des Gegners.",
    "Ein schlimmer Fehlpass von {p} vernichtet den Angriff schon in der eigenen Hälfte.",
    "{p} kommt, schaut sich um — und spielt den Ball ins Aus!",
    "{p} versucht einen Passversuch über das halbe Spielfeld, der aber schon an der eigenen Unfähigkeit scheitert.",
]


# ── Freistoß-Texte ───────────────────────────────────────────────────────────

_FREEKICK_GOAL_TEXTS = [
    "{p} legt sich die Kugel bereit und nimmt Anlauf — TOR! Die Mauer sah dabei nicht gut aus.",
    "Was ein Hammer! {p} haut den Freistoß aus rund 25 Metern ins rechte Eck.",
    "Ein Tor, das das Prädikat Traumtor verdient hat. Der Freistoß von {p} aus halbrechter Position touchiert die Unterlatte und landet im langen Eck.",
    "{p} tritt den direkten Freistoß und trifft — wie ein Strich zieht der Ball über die Mauer hinweg ins Netz.",
    "Ein Freistoß von rechts: {p} entledigt sich seinem Bewacher, gibt einen gezielten Kopfball ab — und der Ball schlägt im kurzen Eck ein.",
]

_FREEKICK_MISS_TEXTS = [
    "{p} schlenzt den Freistoß aus halbrechter Position auf das Tor — der Ball prallt von der Querlatte zurück.",
    "{p} schießt den Freistoß, aber zu ungenau.",
    "{p} zieht ab — Field Goal! Der Ball nimmt den Weg in den Stadionorbit.",
    "Da klingelt es fast im Tor. {p} kommt im Luftkampf an den Ball und drückt ihn knapp an der Torlinie vorbei.",
    "{p} streichelt den Ball noch einmal, bevor er ihn böse tritt — und verfehlt sein Ziel deutlich.",
]


# ── Elfmeter-Texte ───────────────────────────────────────────────────────────

_PENALTY_GOAL_TEXTS = [
    "{p} schreitet an den Punkt — ruhig, konzentriert. Der Torwart ahnt die Ecke nicht. TOR!",
    "Ball hinlegen. Anlauf nehmen. Schuss. Tor! So einfach kann man einen Elfmeter verwandeln. {p} hat alles richtig gemacht.",
    "Ruhig legt sich {p} den Ball hin, guckt sich eine Ecke aus und schickt den Torwart in die andere Richtung — klasse Elfmeter!",
    "Laute Pfiffe, doch {p} macht das souverän — der Ball landet unten in der Ecke.",
    "Ein riesen Druck lastet auf ihm — {p} trifft den Pfosten, doch im Nachschuss trifft er. Der Torwart schaut machtlos hinterher.",
    "Kurioser Elfmeter: {p} rutscht beim Anlauf weg, doch der Ball trudelt langsam unten rechts ins Tor.",
    "{p} schießt mit voller Gewalt an die Latte. Der Torwart feiert schon, bekommt den Ball aber unglücklich an den Rücken — von dort ins Tor.",
    "{p} schreitet an den Punkt, wirkt aber sehr nervös. Schwacher Ball — und doch drin! Der Torwart patzt.",
]

_PENALTY_MISS_TEXTS = [
    "{p} versucht lässig den Ball in die Mitte zu lupfen — der Keeper riecht den Braten und hält.",
    "{p} läuft an und schießt den Ball weit über den Kasten.",
    "{p} läuft an, verzögert kurz — und schießt den Ball an den rechten Pfosten.",
    "{p} läuft an, verzögert kurz — und schießt den Ball an den linken Pfosten.",
    "{p} läuft an, verzögert kurz — und trifft die Querlatte.",
    "{p} läuft an und rutscht unglücklich mit dem Standbein weg. Chance vertan!",
    "Elfmeter für das angreifende Team. {p} tritt an — Gehalten! Das war zu wenig, der Torhüter lenkt den Ball zur Ecke.",
    "Ein präziser Schuss von {p}, doch der Keeper bekommt noch die Finger dran und wehrt ihn zur Ecke ab! Was für eine Heldentat!",
    "Einmal zweiter Stock bitte — dieser Elfmeter von {p} verfehlt sein Ziel um mehrere Meter.",
    "{p} lässt sich viel Zeit. Verzögerter Anlauf, ein ganz schwacher Schuss in die Mitte des Tores — der Torhüter hält problemlos.",
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
    player_pos: str = '',
    assister: str = '',
    assister_pos: str = '',
    second_player: str = '',
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
    is_gk_red_sub: bool = False,
    match_seed: int = 0,
    event_index: int = 0,
) -> str:
    p = player or ''
    a = assister or second_player or ''
    h = team_name or 'das angreifende Team'
    o = opp_name or 'der Gegner'
    score = f'{score_h}:{score_a}'
    ms = match_seed
    ei = event_index

    if evt_type == 'goal':
        is_gk_assister = (assister_pos or '').upper() in _GK_POSITIONS
        is_gk_scorer   = (player_pos or '').upper() in _GK_POSITIONS
        if a:
            return _goal_with_assist(p, a, score, ms, ei, gk_assist=is_gk_assister)
        else:
            return _goal_no_assist(p, score, ms, ei, gk_scorer=is_gk_scorer)

    elif evt_type == 'shot':
        if p:
            return _shuffled_pick(_SHOT_TEXTS, ms, 'shot', ei).format(p=p, a=a, h=h, o=o)
        return "Schussversuch — der Torwart ist auf dem Posten."

    elif evt_type == 'corner':
        if p:
            return _shuffled_pick(_CORNER_TEXTS, ms, 'corner', ei).format(p=p)
        return "Eckstoß — die Abwehr klärt."

    elif evt_type == 'foul':
        if p:
            return _shuffled_pick(_FOUL_TEXTS, ms, 'foul', ei).format(p=p)
        return "Pfiff — Freistoß."

    elif evt_type == 'card':
        if card_type == 'yellow_red':
            return _shuffled_pick(_CARD_YELLOW_RED, ms, 'card_yr', ei).format(p=p)
        elif card_type == 'red':
            return _shuffled_pick(_CARD_RED, ms, 'card_r', ei).format(p=p)
        else:
            return _shuffled_pick(_CARD_YELLOW, ms, 'card_y', ei).format(p=p)

    elif evt_type == 'sub':
        i = in_name or ''
        o_sub = out_name or ''
        slot = target_slot or ''
        if is_gk_red_sub:
            return _shuffled_pick(_SUB_GK_RED, ms, 'sub_gk_red', ei).format(i=i, o=o_sub)
        elif is_injury_sub:
            return _shuffled_pick(_SUB_INJURY, ms, 'sub_inj', ei).format(i=i, o=o_sub)
        elif position_relation == 'FP' and slot:
            return _shuffled_pick(_SUB_FP, ms, 'sub_fp', ei).format(i=i, o=o_sub, slot=slot)
        elif position_relation == 'NP' and slot:
            return _shuffled_pick(_SUB_NP, ms, 'sub_np', ei).format(i=i, o=o_sub, slot=slot)
        else:
            return _shuffled_pick(_SUB_HP, ms, 'sub_hp', ei).format(i=i, o=o_sub)

    elif evt_type == 'injury':
        if days and days > 7:
            return _shuffled_pick(_INJURY_SUB_TEXTS, ms, 'inj_sub', ei).format(p=p)
        return _shuffled_pick(_INJURY_TEXTS, ms, 'injury', ei).format(p=p)

    elif evt_type == 'tackle_win':
        txt = _shuffled_pick(_TACKLE_WIN_TEXTS, ms, 'tackle_win', ei)
        return txt.format(p=p, a=a or 'dem Gegner')

    elif evt_type == 'tackle_loss':
        txt = _shuffled_pick(_TACKLE_LOSS_TEXTS, ms, 'tackle_loss', ei)
        return txt.format(p=p, a=a or 'dem Gegner')

    elif evt_type == 'pass_fail':
        if p:
            return _shuffled_pick(_PASS_FAIL_TEXTS, ms, 'pass_fail', ei).format(p=p)
        return "Fehlpass — der Gegner übernimmt."

    elif evt_type == 'freekick_goal':
        if p:
            return _shuffled_pick(_FREEKICK_GOAL_TEXTS, ms, 'fk_goal', ei).format(p=p, a=a, h=h)
        return "Freistoß — direkt verwandelt! TOR!"

    elif evt_type == 'freekick_miss':
        if p:
            return _shuffled_pick(_FREEKICK_MISS_TEXTS, ms, 'fk_miss', ei).format(p=p)
        return "Freistoß — knapp vorbei."

    elif evt_type == 'penalty_goal':
        if p:
            return _shuffled_pick(_PENALTY_GOAL_TEXTS, ms, 'pen_goal', ei).format(p=p)
        return "Elfmeter verwandelt! TOR!"

    elif evt_type == 'penalty_miss':
        if p:
            return _shuffled_pick(_PENALTY_MISS_TEXTS, ms, 'pen_miss', ei).format(p=p)
        return "Elfmeter verschossen — daneben!"

    elif evt_type == 'extra_time_start':
        return "Anpfiff zur Verlängerung! 30 weitere Minuten werden gespielt."

    elif evt_type == 'extra_time_end':
        return "Abpfiff nach der Verlängerung — es bleibt beim Unentschieden! Es kommt zum Elfmeterschießen."

    elif evt_type == 'penalty_shootout_start':
        return "Das Elfmeterschießen beginnt! Nerven aus Stahl sind jetzt gefragt."

    elif evt_type == 'penalty_scored':
        rd = minute  # minute field reused as round number
        if p:
            phrases = [
                f"Runde {rd}: {p} tritt an — und verwandelt sicher! {score}",
                f"Runde {rd}: Eiskalt! {p} schiebt den Ball ins Netz. {score}",
                f"Runde {rd}: {p} — verwandelt! Kein Problem für den Schützen. {score}",
                f"Runde {rd}: {p} läuft an und trifft! Der Torwart hat keine Chance. {score}",
            ]
            return _shuffled_pick(phrases, ms, 'pen_sd_scored', ei)
        return f"Runde {rd}: Elfmeter verwandelt! {score}"

    elif evt_type == 'penalty_missed':
        rd = minute
        if p:
            phrases = [
                f"Runde {rd}: {p} tritt an — aber verschossen! Welch ein Drama. {score}",
                f"Runde {rd}: Nein! {p} scheitert am Torwart. {score}",
                f"Runde {rd}: {p} läuft an — der Ball geht am Pfosten vorbei! {score}",
                f"Runde {rd}: Verschossen! {p} lässt die Chance liegen. {score}",
            ]
            return _shuffled_pick(phrases, ms, 'pen_sd_missed', ei)
        return f"Runde {rd}: Elfmeter verschossen! {score}"

    elif evt_type == 'penalty_shootout_end':
        home_pen = score_h
        away_pen = score_a
        return (
            f"Das Elfmeterschießen ist beendet! Endstand im Elfmeterschießen: "
            f"{home_pen}:{away_pen}."
        )

    elif evt_type == 'flow':
        return player or f'Spielunterbrechung in Minute {minute}.'

    return f'Spielunterbrechung in Minute {minute}.'


def build_flow_text(
    minute: int,
    match_seed: int,
    flow_index: int = 0,
    h_name: str = '',
    a_name: str = '',
    h_players: list[str] | None = None,
    a_players: list[str] | None = None,
) -> str:
    """Wählt deterministisch einen Spielfluss-Kommentar (anti-repetition via Permutation).

    h_players / a_players sollten nur aktive (nicht ausgewechselte) Spieler enthalten.
    """
    h = h_name or 'Heim'
    a = a_name or 'Gast'
    all_players = (h_players or []) + (a_players or [])

    if all_players and (match_seed % 3 == 0 or flow_index % 3 == 0):
        p_idx = stable_seed(match_seed, 'flow_player', flow_index) % len(all_players)
        p = all_players[p_idx]
        return _shuffled_pick(_FLOW_WITH_PLAYER, match_seed, 'flow_p', flow_index).format(
            p=p, h=h, a=a)
    else:
        return _shuffled_pick(_FLOW_TEAM, match_seed, 'flow_t', flow_index).format(h=h, a=a)
