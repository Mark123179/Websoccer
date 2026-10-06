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
