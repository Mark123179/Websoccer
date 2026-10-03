"""Satzpools v2 (E-T08).

Aufbau-Zeilen werden aus Fragmenten zusammengesetzt (Start + 0–3 Aufbau-Beats), dadurch entstehen
Sätze statt Schablonen. Enden, Standards, Karten haben eigene Pools nach Ebene.
Platzhalter: {p} Hauptakteur, {o} Gegenspieler, {k} Torwart, {a} Passgeber/Vorlage/Eckenschütze, {r} Empfänger,
{team} Sprechname Verein, {opp} Sprechname Gegner, {score} Spielstand, {tally} Elferstand.
Tags: Eintrag nur wählbar, wenn alle Tags im Kontext der Zeile liegen. Einträge ohne Tags immer.
"""
import random
from ..phases import _short

def T(text, *tags):
    return (text, set(tags))

# ---------------------------------------------------------------- Start-Fragmente (Satzanfang, ohne Punkt)
START = {
    'ballgewinn': [
        T("{p} gewinnt den Ball gegen {o}"), T("{p} spitzelt {o} den Ball weg"), T("Ballgewinn {p} gegen {o}"),
        T("{p} setzt sich gegen {o} durch"), T("{p} ist im Zweikampf mit {o} der Stärkere"), T("{p} holt sich den Ball von {o}"),
        T("{p} erobert den Ball gegen {o} und {team} schaltet sofort um", 'umschalten_konter'),
        T("{p} grätscht {o} den Ball weg", 'gegner_zweikampf_hart'), T("{p} bleibt im Duell mit {o} oben"),
    ],
    'pressing_ballgewinn': [
        T("{team} presst {o} beim Aufbau zu, {p} gewinnt den Ball in der gegnerischen Hälfte"),
        T("{p} läuft {o} an, der Pass wird zu kurz – Ballgewinn 30 Meter vor dem Tor"),
        T("Wieder das Pressing: {p} stellt {o} zu und hat den Ball"),
        T("{o} findet unter Druck keinen Abnehmer, {p} schnappt sich den Ball"),
    ],
    'abgefangen': [
        T("{p} fängt den Pass von {o} ab"), T("{p} liest den Pass von {o} und ist dazwischen"),
        T("{o} spielt zu ungenau, {p} nimmt den Ball auf"), T("{p} steht im Passweg von {o}"),
        T("{o} will sofort vertikal spielen, {p} ahnt es und ist zuerst am Ball"),
    ],
    'einwurf': [T("Einwurf {p}"), T("{p} wirft kurz ein"), T("{p} wirft ein")],
    'abstoss': [T("Abstoß {p}"), T("{p} spielt flach heraus", 'aufbau_aus_abwehr'), T("{p} schlägt den Abstoß lang", 'aufbau_lange_baelle'), T("{p} bringt den Abstoß ins Spiel")],
    'nachsetzen': [
        T("{team} bleibt dran"), T("{team} setzt nach"), T("Der Ball bleibt bei {team}"), T("{p} holt sich den zweiten Ball"),
    ],
}

# ---------------------------------------------------------------- Aufbau-Fragmente (Nebensatz, ohne Punkt)
BUILD = {
    'aufbau_pass': [T("{p} baut in Ruhe auf"), T("{p} bringt den Ball nach vorn"), T("über {p} geht es ins Mittelfeld"), T("{p} spielt sicher heraus")],
    'langer_ball': [T("{p} schlägt den langen Ball"), T("{p} spielt weit nach vorn"), T("{p} hebt den Ball über die erste Linie"), T("langer Ball von {p}")],
    'ballzirkulation': [T("{team} lässt den Ball laufen"), T("{p} hält den Ball und wartet auf Bewegung"), T("{team} zieht {opp} mit langen Ballstafetten auseinander"), T("{p} verschleppt das Tempo")],
    'verlagerung': [T("{p} verlagert auf {r}"), T("{p} wechselt die Seite zu {r}"), T("Diagonalball von {p} auf {r}"), T("{p} öffnet das Spiel auf {r}")],
    'steilpass': [T("{p} steckt auf {r} durch"), T("{p} spielt {r} steil an"), T("{p} findet {r} durch die Schnittstelle"), T("Steilpass {p} auf {r}")],
    'doppelpass': [T("{p} und {r} kombinieren sich durch"), T("Doppelpass {p} – {r}"), T("{p} spielt mit {r} auf engem Raum")],
    'zielspieler': [T("{p} sucht {r} als Zielspieler"), T("{r} macht den hohen Ball von {p} fest"), T("{p} hoch auf {r}, der behauptet ihn")],
    'tiefenlauf': [T("{r} startet, {p} spielt ihn an"), T("{p} in den Lauf von {r}"), T("{p} bedient den startenden {r}")],
    'flanke': [T("{p} flankt von links", 'zone_left'), T("{p} flankt von rechts", 'zone_right'), T("{p} bringt den Ball von außen"), T("Flanke {p} auf {r}"), T("{p} zieht die Flanke scharf vors Tor")],
    'dribbling': [T("{p} geht an {o} vorbei"), T("{p} lässt {o} stehen"), T("{p} zieht nach innen, {o} kommt nicht hinterher"), T("{p} nimmt Tempo auf gegen {o}")],
}

# ---------------------------------------------------------------- Einstieg (Ebene 3, eigene Zeile)
ENTRY = {
    'einstieg_steilpass': [
        T("{p} steckt durch – {r} ist frei!"), T("Jetzt wird es gefährlich: {p} spielt {r} in die Schnittstelle."),
        T("{p} sieht den Laufweg von {r} und bedient ihn hinter die Kette."), T("Steilpass {p}, {r} ist durch!"),
    ],
    'einstieg_tiefenlauf': [
        T("{r} startet in die Tiefe, {p} spielt ihn an – Tempo Richtung Tor!"), T("{p} lupft den Ball hinter die Kette, {r} ist durch."),
        T("{r} zieht den Sprint an, {p} findet ihn im richtigen Moment."),
    ],
    'einstieg_flanke': [
        T("{p} bringt den Ball scharf vors Tor, {r} steigt hoch!"), T("{p} kommt bis zur Grundlinie und flankt in die Mitte."),
        T("Hereingabe {p} – im Strafraum lauert {r}."), T("{p} flankt mit Zug in den Fünfmeterraum.", 'fokus_flanke_kopfball'),
        T("{team} sucht die Flanke: {p} bringt den Ball von links.", 'zone_left'), T("{team} sucht die Flanke: {p} bringt den Ball von rechts.", 'zone_right'),
    ],
    'einstieg_dribbling': [
        T("{p} zieht in den Strafraum, {o} kommt zu spät!"), T("{p} tanzt {o} aus und ist im Sechzehner."),
        T("{p} lässt {o} stehen – freie Bahn Richtung Tor!"), T("{p} geht ins Eins-gegen-eins mit {o} und gewinnt es."),
    ],
    'einstieg_doppelpass': [
        T("{p} und {r} spielen sich mit einem Doppelpass durch die Abwehr!"), T("Doppelpass {p} – {r}, und {team} ist im Strafraum."),
    ],
    'einstieg_zielspieler': [
        T("{r} macht den Ball fest und legt ab – {team} ist vorn drin."), T("{p} auf {r}, der lässt prallen, jetzt wird es eng für {opp}."),
    ],
}

# ---------------------------------------------------------------- Enden
END = {
    'tor': [
        T("TOR für {team}! {a} legt quer, {p} schiebt ein – {score}!"), T("TOR! {p} bleibt vor {k} eiskalt und trifft ins lange Eck. {score}!"),
        T("TOOOR! {p} zieht ab, {k} ist ohne Chance. {score}!"), T("Da ist das Tor! {p} vollendet nach Vorarbeit von {a}. {score}!"),
        T("{score}! {p} trifft für {team} – und das nach dieser Druckphase.", 'phase_druck'),
        T("Der Konter sitzt: {a} bedient {p}, {score}!", 'umschalten_konter'),
        T("TOR! {p} nimmt den Ball direkt und jagt ihn an {k} vorbei. {score}!"),
        T("{p} bleibt ruhig, umkurvt {k} und schiebt ein – {score}!"),
    ],
    'tor_konter': [
        T("TOR nach Konter! {a} spielt es schnell, {p} vollendet. {score}!"), T("Umschaltmoment! {a} bedient {p}, der lässt {k} keine Chance – {score}!"),
        T("Schnell umgeschaltet, eiskalt vollendet: {p} trifft, {score}!"),
    ],
    'tor_kopfball': [
        T("TOR! {p} steigt am höchsten und köpft die Hereingabe von {a} ein. {score}!"), T("Kopfballtor! {p} drückt den Ball von {a} über die Linie – {score}!"),
        T("Per Kopf! {p} trifft nach der Flanke von {a}, {k} kommt nicht mehr hin. {score}!"),
        T("Ecke {a}, Kopfball {p} – TOR! {score}!"),
        T("{p} steigt am höchsten und köpft die Hereingabe von {a} ein – {score}."),
        T("{p} drückt die Ecke von {a} per Kopf über die Linie, {score}."),
    ],
    'eigentor': [T("Eigentor! Der Ball springt von {p} ins eigene Netz. {score}.")],
    'elfmeter_tor': [T("{p} verwandelt den Elfmeter sicher. {score}!"), T("Elfmeter – {p} tritt an und trifft, {k} in die falsche Ecke. {score}.")],
    # Ebene 4 – Großchance
    'schuss_gehalten': [
        T("{p} zieht ab – {k} ist unten und hält!"), T("{p} kommt frei zum Abschluss, aber {k} pariert stark!"),
        T("{k} muss sich strecken – Schuss von {p} aus 16 Metern, gehalten!"), T("{p} schießt flach ins Eck, {k} taucht ab und klärt."),
        T("Direktabnahme {p}, {k} reagiert glänzend!"), T("{p} hält aus der Distanz drauf, {k} hat den Ball sicher."),
        T("Riesenchance für {team}! {p} scheitert an {k}.", 'phase_druck'),
    ],
    'schuss_gehalten_ecke': [
        T("{p} hält drauf, {k} lenkt den Ball mit den Fingerspitzen zur Ecke!"), T("Großchance {p}! {k} kann den Schuss gerade noch über die Latte lenken."),
        T("{p} zieht ab, {k} pariert – Ecke für {team}."),
    ],
    'schuss_pfosten': [
        T("PFOSTEN! {p} zieht ab, der Ball knallt ans Aluminium!"), T("Latte! {p} hämmert den Ball an die Querlatte – {k} wäre geschlagen gewesen."),
        T("{p} trifft nur den Pfosten. Zentimeter fehlen."),
    ],
    # Ebene 3
    'schuss_vorbei': [
        T("{p} schießt – knapp vorbei!"), T("{p} zieht aus 18 Metern ab, der Ball rauscht am Pfosten vorbei."), T("Zu hoch, {p} setzt den Ball über das Tor."),
        T("{p} verzieht aus guter Position."), T("{p} schiebt den Ball am langen Pfosten vorbei."), T("{p} trifft den Ball nicht richtig, Abstoß."),
        T("{p} hat die Chance, setzt den Ball aber drüber."),
    ],
    'schuss_geblockt': [
        T("{p} schießt – {o} wirft sich in den Ball."), T("{o} blockt den Abschluss von {p}."), T("{p} zieht ab, {o} steht im Weg."),
        T("Abschluss {p}, {o} bringt das Bein dazwischen."), T("{p} kommt zum Schuss, {o} blockt."),
    ],
    'torwart_klaert': [
        T("{k} kommt weit heraus und klärt vor {p}."), T("Der Ball ist zu lang, {k} ist vor {p} dran."), T("{p} will durchstarten, {k} läuft den Ball ab."),
    ],
    'foul': [
        T("{o} bringt {p} zu Fall – Freistoß {team}."), T("Foul von {o} an {p}, Freistoß."), T("{o} kommt zu spät gegen {p}."),
        T("{o} stoppt {p} nur mit dem Foul.", 'gegner_zweikampf_hart'), T("{o} hält {p} fest, Pfiff."), T("{o} räumt {p} ab.", 'gegner_zweikampf_hart'),
    ],
    'foul_gelb': [
        T("{o} bringt {p} zu Fall – Gelb!"), T("Foul von {o} an {p}, dafür gibt es die Gelbe Karte."), T("{o} kommt zu spät gegen {p} und sieht Gelb."),
        T("Taktisches Foul von {o} an {p} – Gelb, das war klar."), T("{o} räumt {p} ab. Gelbe Karte.", 'gegner_zweikampf_hart'),
    ],
    'foul_freistoss_kurz': [
        T("{o} foult {p} – {a} führt den Freistoß schnell aus."), T("Foul {o} an {p}, {a} spielt den Freistoß kurz weiter."),
        T("{o} stoppt {p} regelwidrig, {a} macht schnell weiter."), T("Freistoß nach Foul von {o} an {p}, {a} bringt den Ball sofort wieder ins Spiel."),
    ],
    'foul_gelbrot': [T("{o} foult {p} – zweite Gelbe, Gelb-Rot! {opp} ist zu zehnt.")],
    'foul_rot': [T("ROT! {o} räumt {p} ab und fliegt vom Platz. {opp} in Unterzahl.")],
    'abbruch_zweikampf': [
        T("{p} will durch, {o} nimmt ihm den Ball ab."), T("{o} stellt {p} und klärt."), T("{p} bleibt an {o} hängen."),
        T("{o} gewinnt das Duell gegen {p}, {opp} hat den Ball."), T("{p} kommt gegen {o} nicht durch."),
        T("{o} stellt den Passweg zu, {team} muss neu aufbauen."),
    ],
    'abbruch_fehlpass': [
        T("Der Pass von {p} kommt zu ungenau – {o} ist dazwischen."), T("{p} spielt den Ball in die Füße von {o}."), T("{o} fängt den Pass von {p} ab."),
        T("{p} sucht {r}, findet aber {o}."), T("Zu hastig: {p} verliert den Ball an {o}."), T("{p} will vertikal spielen, {o} liest den Pass."),
    ],
    'abbruch_abseits': [T("Abseits! {p} startet beim Pass von {a} zu früh."), T("Die Fahne geht hoch – {p} im Abseits."), T("{p} wird angespielt, steht aber im Abseits.")],
    'abbruch_aus': [T("{p} spielt den Ball ins Seitenaus."), T("Zu weit von {p}, Abstoß."), T("{p} bringt die Flanke nicht mehr vors Tor, Abstoß.")],
    'abbruch_aus_ecke': [T("{p} flankt, {o} klärt ins Toraus – Ecke {team}."), T("{o} blockt die Hereingabe von {p} über die Grundlinie. Ecke."), T("{p} versucht es, {o} fälscht ab – Eckball {team}.")],
    # Standards (eine Zeile, {a} = Schütze)
    'ecke_kopfball_vorbei': [T("Ecke {a} – {p} köpft knapp vorbei!"), T("Ecke {a}, {p} steigt hoch, der Kopfball geht drüber."), T("{a} bringt die Ecke, {p} setzt den Kopfball neben das Tor.")],
    'ecke_kopfball_gehalten': [T("Ecke {a} – Kopfball {p}, {k} hält!"), T("{a} tritt die Ecke, {p} nickt aufs Tor, {k} ist da!"), T("Ecke {a}, {p} per Kopf – {k} fängt sicher.")],
    'ecke_kopfball_geblockt': [T("Ecke {a} – {p} köpft, {o} blockt auf der Linie!"), T("{a} bringt die Ecke, {p} kommt zum Kopfball, {o} klärt vor der Linie.")],
    'ecke_gefangen': [T("Ecke {a} – {k} pflückt den Ball aus der Luft."), T("{a} tritt die Ecke, {k} kommt heraus und fängt."), T("Ecke {a}, nichts zu holen: {k} hat den Ball.")],
    'ecke_gefaustet': [T("Ecke {a} – {k} faustet weg."), T("{a} bringt die Ecke, {k} boxt den Ball weg, bevor {p} steigen kann."), T("Ecke {a}, {k} kommt raus und faustet.")],
    'ecke_geklaert': [T("Ecke {a} – {o} köpft heraus."), T("{a} tritt die Ecke, {o} gewinnt das Luftduell gegen {p}."), T("Ecke {a}, {o} klärt per Kopf.")],
    'ecke_kurz': [T("Ecke {a}, kurz ausgeführt auf {r} – {team} baut neu auf."), T("{a} spielt die Ecke kurz auf {r}.")],
    'freistoss_direkt_gehalten': [T("Freistoß {p} über die Mauer – {k} hält im Eck!"), T("{p} zirkelt den Freistoß aufs Tor, {k} pariert!")],
    'freistoss_direkt_vorbei': [T("Freistoß {p} – knapp über die Latte."), T("{p} zieht den Freistoß am Tor vorbei.")],
    'freistoss_direkt_mauer': [T("Freistoß {p} – in die Mauer."), T("{p} schießt den Freistoß in die Mauer, {team} bleibt am Ball.")],
    'freistoss_flanke_geklaert': [T("Freistoß-Flanke {p}, {o} köpft heraus."), T("{p} bringt den Freistoß in den Strafraum, {o} klärt vor {r}.")],
    'freistoss_flanke_kopfball_vorbei': [T("Freistoß {p} auf {r} – Kopfball vorbei."), T("{p} flankt den Freistoß, {r} köpft drüber.")],
    'freistoss_kurz': [T("Freistoß {p}, kurz ausgeführt."), T("{p} spielt den Freistoß kurz weiter.")],
    # Unterbrechungen
    'wechsel': [T("Wechsel {team}: {p} für {o}."), T("{team} wechselt – {o} runter, {p} rein.")],
    'wechsel_torwart': [T("Torwartwechsel bei {team}: {p} ersetzt {o}.")],
    'wechsel_applaus': [T("{o} geht unter Applaus vom Platz, {p} kommt."), T("Starke Partie von {o} – jetzt {p}.")],
    'wechsel_enttaeuscht': [T("{team} reagiert: {o} war nicht im Spiel, {p} kommt."), T("{o} geht mit hängendem Kopf, {p} soll es besser machen.")],
    'wechsel_offensiv': [T("{team} geht ins Risiko: {p} für {o}."), T("Mehr Druck nach vorn – {p} ersetzt {o}.")],
    'verletzung': [T("{p} bleibt liegen und muss behandelt werden."), T("Verletzungspause: {p} kann nicht weiter.")],
    'anpfiff': [T("Anpfiff!")], 'anpfiff_2': [T("Weiter geht's, zweite Halbzeit.")], 'anpfiff_vl': [T("Verlängerung – 30 Minuten mehr.")],
    'halbzeit': [T("Halbzeit. {score}."), T("Pause – es steht {score}.")], 'halbzeit_vl': [T("Seitenwechsel in der Verlängerung.")],
    'abpfiff_90': [T("Nach 90 Minuten steht es {score}. Verlängerung.")], 'abpfiff': [T("Abpfiff! Endstand {score}."), T("Das Spiel ist aus. {score}.")],
    'elfmeterschiessen_start': [T("Elfmeterschießen! Nach 120 Minuten steht es {score}.")],
    'elfer_verwandelt': [T("{p} verwandelt sicher. {tally}."), T("{p} trifft, {k} in der falschen Ecke. {tally}."), T("Drin! {p} bleibt cool. {tally}."), T("{p} – oben rechts, keine Chance für {k}. {tally}."),
                         T("Der erste Treffer: {p} macht es besser. {tally}.", 'erster_treffer_nach_fehlschuss'), T("{p} zeigt, wie es geht – {tally}.", 'erster_treffer_nach_fehlschuss')],
    'elfer_vergeben': [T("{p} schießt vorbei! Es bleibt beim {tally}."), T("{p} setzt den Ball über das Tor. {tally}."), T("{p} scheitert am Pfosten! {tally}."),
                       T("Auch {p} verschießt! Weiter {tally}.", 'auch_vergeben'), T("{p} scheitert ebenfalls – {tally}.", 'auch_vergeben')],
    'elfer_gehalten': [T("{k} hält den Elfmeter von {p}! {tally}."), T("Gehalten! {k} ahnt die Ecke gegen {p}. {tally}."), T("Und wieder nichts: {k} hält gegen {p}. {tally}.", 'auch_vergeben')],
    'elfmeterschiessen_ende': [T("Entschieden im Elfmeterschießen: {tally}.")],
}

# ---------------------------------------------------------------- Tore nach Spielverlauf („Warum jetzt?")
TOR_CTX = {
    'antwort': [
        T("Die schnelle Antwort! {p} trifft, {score} – {team} ist sofort wieder dran."),
        T("Direkt zurückgeschlagen: {p} bleibt vor {k} cool, {score}!"),
        T("Kaum kassiert, schon zurückgeschlagen – {p} macht das {score}."),
    ],
    'doppelschlag': [
        T("Doppelschlag! {p} legt nach – {score}, und {opp} wankt."),
        T("{team} legt sofort nach! {p} trifft zum {score}."),
        T("Und gleich das nächste Tor! {p} – {score}. {opp} ist gerade nicht auf dem Platz."),
    ],
    'nach_druck': [
        T("Es hatte sich angedeutet! {p} belohnt die Druckphase von {team} – {score}."),
        T("Der Druck zahlt sich aus! {p} trifft, {score}!"),
        T("TOR! Nach all den Chancen ist er drin – {p}, {score}."),
    ],
    'aus_dem_nichts': [
        T("Aus dem Nichts! {opp} hatte gerade die besseren Chancen – und dann trifft {p} zum {score}."),
        T("Gegen den Spielverlauf! {p} bringt {team} mit dem {score} in Führung."),
        T("Damit war nicht zu rechnen: ein Angriff, ein Tor – {p}, {score}."),
    ],
    'gedreht': [
        T("{team} hat das Spiel gedreht! {p} trifft zum {score}."),
        T("Komplett gedreht! {p} macht aus dem Rückstand die Führung – {score}."),
        T("TOR! {p} – {score}, {team} führt jetzt, {opp} ist eingebrochen."),
    ],
    'spaeter_ausgleich': [
        T("Der Druck zahlt sich aus! {p} bleibt vor {k} eiskalt – {team} rettet in der {min}. Minute das {score}."),
        T("Später Ausgleich! {p} trifft in der {min}. Minute zum {score}."),
        T("{team} belohnt sich in der Schlussphase: {p}, {score}!"),
    ],
    'spaete_fuehrung': [
        T("Späte Führung! {p} trifft in der {min}. Minute – {score}, {opp} hat kaum noch Zeit."),
        T("Das könnte die Entscheidung sein: {p} in der {min}. Minute, {score}!"),
    ],
    'gegen_drangphase': [
        T("Mitten in die Drangphase von {opp}! {p} schlägt zu – {score}."),
        T("{opp} drückt, {team} kontert – {p} trifft zum {score}!"),
    ],
    'anschluss': [
        T("{team} verkürzt! {p} trifft zum {score}."),
        T("{team} ist wieder dran! {p} macht das {score}."),
        T("Anschlusstreffer! {p} bringt {team} auf {score} heran."),
    ],
    'zurueckgeschlagen': [
        T("{team} schlägt zurück! {p} trifft zum {score} – und das nach der Druckphase von {opp}."),
        T("{opp} war dran, doch {team} trifft: {p}, {score}!"),
    ],
}
TOR_CTX_PREFIX = {
    'antwort': ["Die schnelle Antwort! ", "Direkt zurückgeschlagen: "], 'doppelschlag': ["Doppelschlag! ", "{team} legt sofort nach! "],
    'nach_druck': ["Es hatte sich angedeutet! ", "Der Druck zahlt sich aus! "], 'aus_dem_nichts': ["Aus dem Nichts! ", "Gegen den Spielverlauf! "],
    'gedreht': ["{team} hat das Spiel gedreht! ", "Komplett gedreht! "], 'spaeter_ausgleich': ["Später Ausgleich! ", "{team} belohnt sich in der Schlussphase: "],
    'spaete_fuehrung': ["Späte Führung! "], 'gegen_drangphase': ["Mitten in die Drangphase von {opp}! "],
    'anschluss': ["{team} verkürzt! ", "{team} ist wieder dran! "], 'zurueckgeschlagen': ["{team} schlägt zurück! "],
}

# ---------------------------------------------------------------- Phasen (Ebene 1, nur Text) – mit Intensität
PHASE = {
    'abtasten': [T("Beide Teams tasten sich ab, viel Mittelfeld, wenig Zug zum Tor."), T("Ruhiger Beginn, keine Mannschaft geht früh ins Risiko.")],
    'ruhig': [T("Das Spiel plätschert, beide Teams halten die Ordnung."), T("Wenig Strafraumszenen gerade, der Ball läuft meist zwischen den Sechzehnern.")],
    'zerfahren': [T("Zerfahrene Phase: viele Ballverluste auf beiden Seiten, kein Team findet den Rhythmus."), T("Es geht hin und her, ohne dass eine Seite Kontrolle bekommt.")],
    'druck_1': [T("{team} hat jetzt mehr vom Spiel."), T("{team} kommt besser ins Spiel."), T("{team} wird gefährlicher.")],
    'druck_2': [T("{team} übernimmt zunehmend die Kontrolle."), T("{team} erhöht jetzt den Druck."), T("Druckphase {team}."), T("{team} setzt sich in der Hälfte von {opp} fest.")],
    'druck_3': [T("{team} schnürt {opp} hinten ein."), T("Druckphase {team} – {opp} kommt kaum noch zu Entlastung."), T("Eine Angriffswelle nach der anderen: {team} drückt {opp} an den eigenen Strafraum.")],
    'streak': [T("{team} bleibt am Drücker."), T("{team} lässt nicht locker."), T("{opp} bekommt {team} weiterhin nicht unter Kontrolle.")],
    'streak_nach_tor': [T("{team} bleibt nach dem Führungstor am Drücker."), T("{team} setzt nach dem Tor sofort nach."), T("{team} will gleich das nächste – {opp} wankt.")],
    'schlussdrang': [T("{team} drängt jetzt auf {ziel}."), T("Schlussphase – {team} wirft sich noch einmal nach vorn, {ziel} liegt in der Luft."), T("{team} will {ziel} noch vor dem Abpfiff.")],
    'schlagabtausch': [T("Offener Schlagabtausch! Chancen auf beiden Seiten."), T("Jetzt geht es hin und her, beide Teams verzichten auf Absicherung.")],
    'verwalten_1': [T("{team} nimmt etwas Tempo raus, {opp} versucht zu kommen."), T("{team} verwaltet, {opp} sucht die Lücke.")],
    'verwalten_2': [T("{team} nimmt das Tempo raus und verwaltet die Führung."), T("{team} hält den Ball in den eigenen Reihen, {opp} muss kommen.")],
    'verwalten_3': [T("{team} zieht sich zurück und macht die Räume eng – {opp} rennt an, ohne durchzukommen."), T("{team} lässt {opp} kommen und steht sicher.")],
    'schlussoffensive_1': [T("{team} geht jetzt mehr Risiko."), T("{team} rückt weiter auf, {opp} steht tiefer.")],
    'schlussoffensive_2': [T("Schlussoffensive {team} – die Absicherung wird dünner."), T("{team} drängt auf den Treffer, {opp} lauert auf Konter.")],
    'schlussoffensive_3': [T("{team} wirft jetzt alles nach vorn!"), T("{team} riskiert alles – {opp} kommt kaum noch aus dem eigenen Strafraum.")],
    'offen_raeume': [T("{team} öffnet jetzt komplett – dadurch bekommt {opp} immer mehr Räume."), T("{team} geht ins Risiko, {opp} nutzt die Räume und bleibt gefährlich."), T("{team} rückt weit auf – und läuft in die Konter von {opp}.")],
    'pressing_note': [T("{team} presst {opp} früh an – immer wieder Ballgewinne in gefährlichen Zonen."), T("Das hohe Pressing von {team} macht {opp} den Aufbau schwer.")],
}

PLAN_TEXT = {
    'plan_aggressiv_risiko': "{team} stellt um: Bei {score} geht es jetzt aggressiv und mit Risiko nach vorn.",
    'plan_schlussangriff': "Schlussangriff bei {team}! Beim Stand von {score} wird alles nach vorn geworfen.",
    'plan_kontrolle_ballbesitz': "{team} nimmt das Tempo raus: Kontrolle über Ballbesitz, wenig Risiko.",
    'plan_kompakt_sichern': "{team} sichert ab: beide Ketten rücken zusammen, {score} soll verwaltet werden.",
    'plan_zeitspiel': "Zeitspiel bei {team} – jede Unterbrechung wird genutzt, {score} soll reichen.",
    'plan_unterzahl_kompakt': "{team} zieht sich in Unterzahl zurück und macht die Räume eng.",
    'plan_ausgewogen': "{team} kehrt zur Grundausrichtung zurück.",
}
FOKUS_SATZ = {'ausgewogen': "ohne festen Schwerpunkt", 'fluegelspiel': "mit Fokus auf die Flügel", 'ueber_halbraeume': "über die Halbräume", 'durch_mitte': "durch die Mitte",
              'ueber_rechts': "über rechts", 'ueber_links': "über links", 'flanke_kopfball': "mit Flanken auf die Kopfballstarken"}
UMSCHALT = {'konter': "auf Konter", 'ausgewogen': "ausgewogen im Umschalten", 'ballbesitz': "auf Ballbesitz"}
PRESS = {'passiv': "passivem Pressing", 'normal': "mittlerem Pressing", 'intensiv': "intensivem Pressing", 'hoch': "hohem Pressing"}
DECK = {'raum': "Raumdeckung", 'mann': "Manndeckung", 'hybrid': "gemischter Deckung"}
CONNECT = [", ", " – ", ", "]


class Renderer:
    def __init__(self, ctx, rng):
        self.ctx = ctx
        self.rng = rng
        self.recent = {}      # kind -> zuletzt genutzte Texte
        self.mentioned = {}   # seq -> ids
        self.names = {}       # id -> name

    @staticmethod
    def _needs(text):
        return {c for c in ('p', 'o', 'k', 'a', 'r') if '{' + c + '}' in text}

    def _pick(self, pool, kind, tags, ids=None):
        entries = pool.get(kind)
        if not entries:
            return None
        if ids is not None:
            have = {k for k, v in ids.items() if v is not None}
            entries = [e for e in entries if self._needs(e[0]) <= have] or [e for e in pool.get(kind) if not self._needs(e[0])]
            if not entries:
                return None
        elig = [e for e in entries if e[1] <= tags] or [e for e in entries if not e[1]] or entries
        rec = self.recent.setdefault(kind, [])
        fresh = [e for e in elig if e[0] not in rec]
        e = self.rng.choice(fresh or elig)
        rec.append(e[0])
        keep = max(2, len(entries) - 1)
        if len(rec) > keep:
            rec.pop(0)
        return e[0]

    def name(self, pid, seq):
        if pid is None:
            return "ein Spieler"
        full = self.names.get(pid, "ein Spieler")
        seen = self.mentioned.setdefault(seq, set())
        if pid in seen and ' ' in full:
            return full.split(' ')[-1]
        seen.add(pid)
        return full

    def _rep(self, line, actors_ids):
        team = self.ctx.team(line.team) if line.team else None
        opp = self.ctx.opp(line.team) if line.team else None
        rep = {k: self.name(actors_ids.get(k), line.seq) for k in ('p', 'o', 'k', 'a', 'r')}
        rep.update({'team': _short(team.name) if team else '', 'opp': _short(opp.name) if opp else '',
                    'score': line.payload.get('score', ''), 'tally': line.payload.get('tally', '')})
        return rep

    def compose_aufbau(self, line):
        tags = set(line.tags)
        parts = []
        for b in line.payload['beats'][line.payload.get('silent', 0):]:
            pool = START if b['kind'] in START else BUILD
            t = self._pick(pool, b['kind'], tags, ids=b['actors'])
            if t is None:
                continue
            parts.append(t.format(**self._rep(line, b['actors'])))
        if not parts:
            return ''
        prefix = ''
        if 'antwort' in tags and self.rng.random() < 0.7:
            prefix = self.rng.choice(["Die Antwort von {team}: ", "{team} will sofort zurückschlagen: ", "{team} reagiert: "]).format(**self._rep(line, {}))
        elif 'nachsetzen' in tags:
            prefix = self.rng.choice(["{team} bleibt dran: ", "{team} setzt nach: ", "Und wieder {team}: "]).format(**self._rep(line, {}))
        elif 'nachsetzen_lang' in tags:
            prefix = self.rng.choice(["{opp} bekommt {team} weiterhin nicht unter Kontrolle: ", "{team} lässt nicht locker: "]).format(**self._rep(line, {}))
        s = parts[0]
        for i, p in enumerate(parts[1:]):
            s += CONNECT[i % len(CONNECT)] + p
        return (prefix + s).rstrip('.') + '.'

    def render(self, line):
        tags = set(line.tags)
        ids = {k: (v.id if v else None) for k, v in line.actors.items()}
        if line.cls == 'analysis':
            return self.analysis(line)
        if line.cls == 'phase':
            key = line.payload.get('phase')
            lvl = line.payload.get('phase_level', 1)
            if key == 'streak' and line.payload.get('after_goal'):
                key = 'streak_nach_tor'
            t = self._pick(PHASE, f"{key}_{lvl}", tags) or self._pick(PHASE, key, tags)
            rep = self._rep(line, {}); rep['ziel'] = line.payload.get('ziel', 'die Führung')
            return t.format(**rep) if t else ''
        if line.kind == 'aufbau':
            return self.compose_aufbau(line)
        if line.kind.startswith('einstieg_'):
            b = line.payload['beats'][line.payload.get('silent', 0)]
            t = self._pick(ENTRY, line.kind, tags, ids=b['actors'])
            return t.format(**self._rep(line, b['actors'])) if t else ''
        kind = line.kind
        if kind == 'foul' and line.payload.get('card'):
            kind = 'foul_' + {'yellow': 'gelb', 'yellow_red': 'gelbrot', 'red': 'rot'}.get(line.payload['card'], 'gelb')
        if kind == 'anpfiff' and line.payload.get('referee'):
            return f"Anpfiff! Schiedsrichter {line.payload['referee']} gibt das Spiel frei."
        gctx = line.payload.get('goal_ctx')
        rep = self._rep(line, ids)
        rep['min'] = str(line.payload.get('minute', line.minute))
        if line.cls == 'goal' and gctx and gctx != 'normal' and gctx in TOR_CTX:
            if kind == 'tor_kopfball' or self.rng.random() < 0.35:
                calm = {k_: [e for e in v if not e[0].lstrip().upper().startswith(('TOR', 'TOO', 'DA IST', 'KOPFBALLTOR', 'PER KOPF')) and 'TOR!' not in e[0].upper()] for k_, v in END.items() if k_.startswith('tor')}
                base = self._pick(calm, kind, tags, ids=ids)
                pre = self.rng.choice(TOR_CTX_PREFIX[gctx]).format(**rep)
                if base:
                    return pre + base.format(**rep)
            t = self._pick(TOR_CTX, gctx, tags, ids=ids)
            if t:
                return t.format(**rep)
        t = self._pick(END, kind, tags, ids=ids)
        if t is None:
            return f"[{kind}]"
        txt = t.format(**rep)
        if line.payload.get('nachsetzen'):
            pre = self.rng.choice(["{team} bleibt dran – ", "Zweiter Ball {team}: ", "{team} setzt nach: "]).format(**self._rep(line, {}))
            txt = pre + txt
        return txt

    def analysis(self, line):
        p = line.payload
        ctx = self.ctx
        team = ctx.team(line.team) if line.team else None
        if line.kind == 'analyse_ausrichtung':
            t = team.tactic
            s = f"{_short(team.name)} ({p['formation']}) spielt {FOKUS_SATZ.get(t.attack_focus, t.attack_focus)}, {UMSCHALT.get(t.umschalten, t.umschalten)}, mit {PRESS.get(t.pressing_level, t.pressing_level)} und {DECK.get(t.deckung, t.deckung)}"
            extra = {'lange_baelle': "lange Bälle aus der Abwehr", 'aus_abwehr': "geordneter Aufbau", 'direkt_vorne': "direktes Spiel nach vorn"}.get(t.buildup_defense)
            zk = {'hart': "harte Zweikämpfe", 'vorsichtig': "vorsichtige Zweikämpfe"}.get(t.zweikampf)
            bits = [x for x in (extra, zk) if x]
            return s + ("; " + ", ".join(bits) if bits else "") + "."
        if line.kind == 'analyse_halbzeit':
            h, a = ctx.home, ctx.away
            sh, co, po = p['shots'], p['corners'], p['possession']
            zh, za = p['zones']
            def zone_txt(z):
                tot = max(1, sum(z.values())); best = max(z, key=z.get)
                return {'left': 'über links', 'right': 'über rechts', 'center': 'durch die Mitte'}[best], round(100 * z[best] / tot)
            th, ph = zone_txt(zh); ta, pa = zone_txt(za)
            return (f"Zwischenbilanz: {p['score']}. Schüsse {sh[0]}:{sh[1]}, Ecken {co[0]}:{co[1]}, Ballbesitz {po[0]}:{po[1]} Prozent. "
                    f"{_short(h.name)} greift vor allem {th} an ({ph} Prozent), {_short(a.name)} {ta} ({pa} Prozent).")
        if line.kind == 'analyse_halbzeitwechsel':
            parts = [f"{k}: {v[0]} → {v[1]}" for k, v in p['changes'].items()]
            return f"{_short(team.name)} stellt zur Pause um – " + ", ".join(parts) + "."
        if line.kind == 'analyse_fazit':
            out = [f"Fazit: {p['score']}."]
            for side in ('home', 'away'):
                t = p['teams'][side]
                s = f"{_short(t['name'])}: {t['shots']} Schüsse ({t['on_target']} aufs Tor), xG {t['xg']}, Ballbesitz {t['possession']} Prozent"
                if t['focus_share'] is not None:
                    s += f"; wollte {t['focus']} – {t['focus_share']} Prozent der Angriffe kamen dort auch"
                if t['pressing_wins']:
                    s += f"; {t['pressing_wins']} Ballgewinne im Pressing"
                if t['pressing_bypassed']:
                    s += f", {t['pressing_bypassed']}-mal überspielt"
                for plan, st in t['plans'].items():
                    s += f"; Plan „{plan}“ ({st.get('minutes', 0)} Min): {st.get('shots_for', 0)} Schüsse, {st.get('goals_for', 0)}:{st.get('goals_against', 0)} Tore"
                out.append(s + ".")
            return " ".join(out)
        if line.kind.startswith('plan_'):
            return PLAN_TEXT.get(line.kind, "{team} stellt um.").format(team=_short(team.name) if team else '', score=p.get('score', ''))
        return ''


def render_all(lines, ctx, rng):
    r = Renderer(ctx, random.Random(ctx.match_id * 31 + 5))
    for t in (ctx.home, ctx.away):
        for p in t.players.values():
            r.names[p.id] = p.name
    for ln in lines:
        ln.text = r.render(ln)
