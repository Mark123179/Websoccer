---
name: Arbeitsliste bei Paket-Reupload
description: Nutzerentscheidungen zu stabilen Einträgen, Handeinträgen und datenabhängigen Einzelsperren aus Nachträgen 9 und 10.
---

Ein Arbeitslisteneintrag gehört zum Verein, nicht zum Upload. Sein Hauptschlüssel besteht aus Verein, Gegenstandsart, Gegenstandsbezug und Feld. Bei einer einzelnen Lücke sind Text und Schwere keine Schlüsselbestandteile. Mehrere Lücken zum selben Hauptschlüssel erhalten nach Nachtrag 10 einen Unter-Schlüssel aus dem exakten Text.

**Why:** Ein Upload darf die bisherigen Erledigt-Status und Nacharbeiten nicht verlieren oder dieselbe Lücke duplizieren.

**How to apply:** Gleiche Lücke behält Zeile und Status. Fehlende Lücke wird nachvollziehbar durch neues Paket erledigt. Neue Lücke wird offen angelegt. Wiederkehr öffnet einen paketgeschlossenen Eintrag erneut; eine handerledigte Lücke bleibt erledigt, solange der Handeintrag erhalten bleibt. Beim Wechsel Einzel-/Mehrfachlücke den gleichtextigen Eintrag bewahren und die übrige Historie erhalten. Alle Eintragsarten einschließlich Prüfpool und fehlender Bilder mitführen.

Handeinträge füllen Lücken, das Paket gewinnt bei gelieferten Werten.

**Why:** Mark hat getrennt entschieden, dass Nachpflege bei fehlenden Paketwerten erhalten bleiben soll, aber kein dauerhaftes Veto gegen neue Quellwerte darstellt.

**How to apply:** Ohne Paketwert bleibt von_hand erhalten; bei identischem Wert wird gefunden übernommen, ohne Konfliktanzeige. Bei anderem Wert Paketwert übernehmen und Alt-/Neuwert vorher in der Vorschau zeigen. Identitätswechsel niemals automatisch zusammenführen.

Einzelsperren sind aus benötigten Quellwerten und berechneter Stärke abzuleiten, nicht allein aus den Paketlücken.

**Why:** Eine manuell ergänzte ID liefert noch kein Rating und darf nicht die Aufstellbarkeit vortäuschen.

**How to apply:** N48 sperrt bei FM/TM/CMTRACKER-Status nicht_gefunden, vorhandener FM-/CMTRACKER-ID ohne Rating oder fehlender berechneter Stärke. CMTRACKER nicht_vorhanden allein sperrt nicht. Solche Einträge sind nicht von Hand abhakbar und schließen sich mit dem Wegfall der Daten-Sperre. Vor Bestätigung zeigt die Vorschau neue, bleibende und durch Paket geschlossene Einträge.

Nachgewiesenes CMTracker-nicht_vorhanden gilt ebenso für Profis: FMInside allein ist zulässig, ohne dadurch verursachte Sperre oder Lücke. Ein Profi ohne FMInside erhält hingegen eine Einzelsperre, niemals allein deshalb eine Ligasperre.

**Why:** Nachtrag 14 erweitert die bestätigten Quellregeln auf Fälle weiterer Vereine; die Stärkeformel und datenabhängige Sperrregel bleiben unverändert.

**How to apply:** Nichtvorhandensein von erfolgloser Suche unterscheiden und andere Sperrgründe erhalten. Die Validierungsergänzung blockiert nicht die BVB-v3-Umstellung, muss aber vor dem ersten betroffenen weiteren Vereinsimport fertig sein. BVB-v3 nicht neu bauen.

Die Anzeige bürgerlicher Namen statt display_name zunächst nur inventarisieren; jede Änderung daran benötigt Marks nachfolgende Entscheidung.

**Why:** Nachtrag 14 autorisiert die Prüfung ausdrücklich, nicht die Änderung der Namensanzeige.

**How to apply:** Listen, Aufstellung, Ticker und Suche getrennt berichten. Paketseitige Regeln zu Namen, Leihende und Marktwert-Vereins-ID sind kein Auftrag für neue serverseitige Ersatzwert- oder Namensmatching-Logik.

Die beim Leihverein vergebene Rückennummer bleibt dem Spieler erhalten, auch
bei seiner Rückkehr zum Stammverein. Ein leerer Nummernwert im Paket des
Stammvereins darf die vorhandene Nummer nicht löschen.

**Why:** Der Nutzer hat ausdrücklich klargestellt: Ibrahimovic ist von Bayern
an Augsburg verliehen, Augsburg gibt ihm die 21; er behält sie auch bei der
Rückkehr zu Bayern.

**How to apply:** Importreihenfolge und Leihrückkehr dürfen diesen Nummernerhalt
nicht verletzen. Diese fachliche Festlegung ist kein Nachweis einer bereits
umgesetzten technischen Korrektur.
