# Replit-Auftrag: Modul „Show-Auktion"

## Was du bekommst

| Paket | Inhalt |
|---|---|
| **Design-Paket** (Claude Design) | `Auktionen.dc.html` (Haupt-Template: Bühne + Detailseite + Gebots-Modal), `export/Auktionen-standalone.html` (alles inline, sofort lauffähig), `auto-cutout.js`, `image-slot.js`, `assets/`, `_ds/` (Design-System-Tokens), `export/Projektdokumentation.md` |
| **Spec-Paket** | `SPEC_Show-Auktion.md` (**verbindlich**), `GESPRAECHSVERLAUF_Show-Auktion.md` (Begründungen), dieser Prompt |

**Rangfolge bei Widersprüchen:** `SPEC_Show-Auktion.md` schlägt Design-Paket schlägt Projektdokumentation. Die Projektdokumentation ist der Stand *vor* dieser Designsession und enthält überholte Punkte (siehe „Bekannte Abweichungen" unten).

---

## Auftrag

Baue das Modul **Show-Auktion** als eigenständige Django-App unter dem bestehenden Navigationspunkt **Transfers → Auktionen**. Es ist kein Umbau des offenen Transfermarkts — dieser bleibt unverändert.

Kurzfassung: Der Creator wählt 1–5 Spieler aus der bestehenden Datenbank und versteigert sie in parallelen Auktionen unterschiedlichen Typs, präsentiert im Stil einer TV-Transfershow. Der Erlös ist eine Senke.

---

## Die zentrale Architekturvorgabe

**Es darf keinen typspezifischen Code geben.**

Ein Auktionstyp ist ausschließlich eine Belegung von 16 Parameter-Achsen (Spec §3), gespeichert als validiertes JSON. Fünf Presets sind zum Start anzulegen (Spec §4), aber weder Backend noch Frontend dürfen die Typnamen kennen. Der Creator muss später über die Oberfläche neue Typen anlegen können — **ohne Migration, ohne Deployment, ohne Code**.

Konkret heißt das:
- Keine `if auction.type == 'undercover'`-Verzweigungen. Verzweigt wird über Achsenwerte.
- Das Frontend rendert drei Slots (Preis / Zeit / Aktion), deren Ausprägung sich aus Achse 1–7 und 15 ableitet.
- Neue Achsenwerte sind zulässig; neue Achsen sind ein Spec-Update.

Wenn du an eine Stelle kommst, an der ein Typ einen Sonderfall zu brauchen scheint: **das ist ein Signal, dass eine Achse fehlt.** Melde es zurück, statt den Sonderfall einzubauen.

---

## Reihenfolge der Umsetzung

### Stufe 1 — Datenmodell & Grammatik
1. Django-App anlegen, Route unter *Transfers → Auktionen*
2. Models `ShowAuctionPreset`, `ShowAuction`, `ShowAuctionBid`, `ShowAuctionWatch` (Spec §6)
3. JSON-Schema-Validierung für `config` inkl. der Regeln aus §6.1
4. Fünf Start-Presets als Data-Migration (Spec §4)
5. Spielerstatus „Raum": Statuswert am Spieler plus Anpassung der Default-QuerySets, sodass Auktionsspieler aus Scouting, Transfermarkt und Spielersuche verschwinden — **nicht** als Flag, das jede Query einzeln respektieren muss (Spec §6.5)

**Wichtig:** Ermittle im Bestand, welche Manager/QuerySets betroffen sind, und liste sie im Abschlussbericht auf.

### Stufe 2 — Gebotslogik & Finanzanbindung
6. Gebotsabgabe exakt nach Prüfreihenfolge Spec §8.1, in **einer** Transaktion mit `select_for_update` auf die Auktion
7. Geld- und Kaderplatz-Reservierung **über den zentralen Buchungsservice des Finanzsystems** — keine eigene Kontologik, keine zweite Wahrheit über „verfügbar"
8. Freigabelogik nach Achse 16 (`bei_ueberbietung` / `bei_auktionsende` / `sofortige_buchung`)
9. Änderung verdeckter Gebote mit Reservierungsanpassung (Spec §8.2)
10. Preisformel für fallende Auktionen — **berechnet, nicht getickt**, identisch in Backend und Frontend (Spec §4.3)

### Stufe 3 — Lebenszyklus & Beendigung
11. Ein Celery-Beat-Task, Intervall 60 Sekunden, für `scheduled → running` und fällige Beendigungen. **Kein Task pro Auktion, kein `apply_async(eta=...)`** — die Begründung steht in §10 und im Gesprächsverlauf Frage 12
12. Lazy-Auswertung beim Seitenaufruf für die Lücke zwischen Beat-Läufen
13. Idempotente Buchungsreferenz `showauction:{auction_id}:settle` mit Unique-Constraint
14. Gewinnerermittlung nach Achse 15 inkl. Losentscheid bei Gleichstand
15. Zuschlag: Buchung als Senke → Spieler verlässt den Raum → regulärer Transfer → Transferhistorie „Vereinslos → Gewinnerverein" → 21-Tage-Wechselsperre → **keine** Jugendabgabe
16. Platzen: Spieler zurück in den Normalbestand, alle Reservierungen frei

### Stufe 4 — Frontend
17. Design aus dem Paket übernehmen. **Breitenverhalten und Einbettung in die App-Shell löst du** (das Design hat bewusst keine feste Breite).
18. Bühne: Sortierung nach geringster Restzeit (Mitte = dringendste), Typ-Chip, Endspurt-Badge, Name, Live-Countdown. **Statusfrei** — keine manager-bezogenen Anzeigen (bewusste Entscheidung E19).
19. Detailseite mit den drei Slots, Live-Countdown, Positionsfeld, Regelpanel
20. Alle Spielerdaten aus der bestehenden Datenbank verlinken, nichts duplizieren: Name → Spielerprofil, Wappen/Vereinsname → Verein, Liga → Liga. Die Platzhalter-Routen im Template (`#/spieler/{id}` usw.) durch echte ersetzen.
21. Sperrgrund bei fehlender Teilnahmeberechtigung **vor** dem Gebots-Button anzeigen, Button deaktiviert (E20)
22. Bietergefecht-Hitzemesser nach Formel §13; bei verdeckten Typen nur der Zeiger, nie Zahlen
23. **Entfernen:** Kloppo-Moderationstexte und TV-Laufband. **Entfernen:** Demo-Auktionen Kimmich/Saliba.

### Stufe 5 — Creator Mode
24. Auktion anlegen: Spieler per **Textsuchfeld** aus der bestehenden DB verknüpfen (keine Neuanlage), Preset wählen, Parameter überschreiben, Teilnahmebedingungen setzen, Hero-Bild hochladen, Medienlogo hochladen, Startzeit setzen
25. **Config-Snapshot beim Anlegen einfrieren** — spätere Preset-Änderungen dürfen laufende Auktionen niemals rückwirkend verändern
26. Spieler betritt den Raum **beim Anlegen**, nicht beim Start
27. Korridor der Bereichsauktion beim Anlegen zufällig ziehen, Spanne im Formular editierbar
28. Hero-Bild serverseitig freistellen (z. B. `rembg`), analog zur Browser-Demo mit Torso-Normierung und Bodenverankerung. Das Bild landet **nie** in der Spielerdatenbank. Logo-Slots werden **nie** freigestellt.
29. Preset-Verwaltung: Anlegen/Bearbeiten/Deaktivieren von Auktionstypen über die 16 Achsen

### Stufe 6 — Benachrichtigungen
30. Gebot setzt den Manager automatisch auf die Beobachtungsliste (manuell entfernbar)
31. Zustellung ausschließlich über die **In-Game-Glocke** (Forum-Infrastruktur), **ungebündelt**
32. Ereignisse: neues Gebot, Überbietung, Auktionsstart, Auktionsende, geplatzt, Endspurt-Beginn

---

## Nicht bauen

E-Mail-Benachrichtigungen · Web-Push/VAPID · Kloppo-Moderationstexte · TV-Laufband · Manager-Status auf der Bühne · Auktions-Historie / Hall of Fame / Datencenter-Anbindung · Tausch-Gebote · Multi-Lot · Verkäufer-Hammer oder -Ablehnung · automatischer Auktions-Rhythmus.

---

## Bekannte Abweichungen der Projektdokumentation vom aktuellen Stand

Die `Projektdokumentation.md` im Design-Paket ist der Stand vor dieser Session. Diese Punkte sind überholt:

| Projektdoku sagt | Gilt jetzt |
|---|---|
| Drei Typen: 24h-halten, Deadline/Stich, Undercover | Fünf Presets: Halte, Undercover, Holländisch, Bereich, Blitz. Klassische Deadline ist **nicht** im Start-Set |
| Deadline-Auktion = Creme | Creme gehört zur **Bereichsauktion** |
| Kloppo-Features inkl. Laufband | Laufband und Moderationstexte gestrichen, **Hitzemesser bleibt** |
| Sender-Logo je Auktionstyp festlegen | Medienmarke ist **frei pro Auktion**, unabhängig vom Typ |
| Bild wird nach Auktionsende gelöscht | Bleibt so (Archivierung ist ein späteres, eigenes Feature) |
| Auktionstypen im Creator Mode verwalten (Punkt 5 der To-dos) | Kern der Architektur, nicht optional |

---

## Abnahmekriterien

1. Ein neuer Auktionstyp lässt sich **allein über die Creator-Mode-Oberfläche** anlegen und läuft korrekt — ohne Codeänderung. Teste das mit „Undercover mit Zweitpreis-Zuschlag" (Achse 11 = `zweithoechstes_plus_erhoehung`).
2. Zwei gleichzeitige Gebote auf denselben Betrag erzeugen keinen inkonsistenten Zustand.
3. Ein `docker compose up -d --force-recreate web` mitten in einer laufenden Auktion verändert deren Ablauf nicht.
4. Eine Auktion kann unter keinen Umständen zweimal beendet oder zweimal gebucht werden.
5. Ein Spieler in einer laufenden Auktion ist über Scouting, Transfermarkt und Spielersuche nicht auffindbar.
6. Eine Preset-Änderung während laufender Auktionen verändert diese nicht.
7. Ein Manager kann nicht mehr Geld binden, als er hat — auch nicht über Show-Auktionen und Normalmarkt zusammen.
8. Der angezeigte Preis einer holländischen Auktion stimmt immer mit dem gebuchten überein.
9. Eine Bereichsauktion ohne Korridortreffer platzt sauber und gibt alle Reservierungen frei.

---

## Rückmeldung

Liefere am Ende:
- Liste der angepassten QuerySets/Manager für den „Raum"
- Liste aller Stellen, an denen du dich gegen die Spec entschieden hast, mit Begründung
- alle Punkte, an denen du eine fehlende Achse vermutet hast
- fehlende Assets (Liga-Logos Premier League, Vereinswappen Liverpool/Arsenal)
