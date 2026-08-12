# Transfersystem — Übergabepaket für Replit

## Was hier drin ist

| Datei | Zweck |
|---|---|
| `Transfersystem-standalone.html` | **Der Prototyp.** Eine einzige Datei (Doppelklick im Browser). Wappen, Spielerfotos, Platzhalter und Wettbewerbslogo sind eingebettet; **nur die Nationalflaggen werden von `flagcdn.com` geladen** (dafür ist Internet nötig). **Das ist die verbindliche visuelle Referenz.** |
| `TRANSFERSYSTEM_SPEC.md` | **Die Bauanleitung.** Alle Regeln, Zahlen, Screens, Popups, Push-Auslöser, Datenmodell, Cronjobs, Design-Tokens, Abnahme-Checkliste. |
| `Transfersystem.dc.html` | Quelldatei des Prototyps (Markup + Logik lesbar, falls exakte Werte/Styles nachgeschlagen werden sollen). |
| `assets/` | Wappen, Spielerfotos, Platzhalter, Wettbewerbslogo (identisch zu den Pfaden im Websoccer-Repo). |

## Arbeitsauftrag für Replit

1. **`TRANSFERSYSTEM_SPEC.md` vollständig lesen**, bevor eine Zeile Code entsteht. Die Datei ist verbindlich.
2. **`Transfersystem-standalone.html` im Browser öffnen und jeden Reiter durchklicken** — Layout, Farben, Abstände, Texte, Reihenfolgen, Interaktionen sind so zu übernehmen.
3. Nachbau als **Django-Templates + CSS** im bestehenden Projekt (`game/templates/game/…`, `game/static/game/css/…`), passend zum vorhandenen Management-Bereich. Kein React in Produktion.
4. **1:1 nachbauen.** Keine Interpretationen, keine Halluzinationen, keine „Verbesserungen", keine erfundenen Felder oder Buttons. Was nicht in Spec/Prototyp steht, wird nicht gebaut.
5. Am Ende **Abnahme-Checkliste (§ 13.6 der Spec) Punkt für Punkt durchgehen.**

## Wichtige Randbedingungen

- **Bestehende Bereiche bleiben unberührt:** Scouting und Beobachtungsliste werden ausschließlich als Reiter in die neue Leiste eingehängt, ihr Inhalt wird nicht angefasst.
- **Sprache:** komplett Deutsch, Zahlen deutsch formatiert (`21.500.000 €`).
- **Design-System „MatchEngine"**: Tokens in § 13.2 der Spec; im Repo unter `game/static/game/css/global-dashboard/*`.
- **Mock-Daten im Prototyp sind Beispiele** (Spielernamen, Beträge, Vereine). Die *Struktur* ist verbindlich, die *Werte* kommen aus der Datenbank.
- **Phase 2 (§ 12 der Spec — Weiterverkaufsbeteiligung & Rückkaufoption):** Regeln sind festgeschrieben, aber **noch nicht bauen**, solange nicht ausdrücklich beauftragt.
- **Nationalflaggen im Nachbau:** im Prototyp `https://flagcdn.com/w40/<iso2>.png`. Im Produktivsystem stattdessen die vorhandenen Repo-Assets `staticfiles/assets/flags/<asset_id>.png` über die bestehende Nationalitäts-Zuordnung verwenden (Größe 18×12 px, `border-radius:2px`, `object-fit:cover`, 1px dunkler Rahmen — wie im Prototyp).
- **Offene Todos außerhalb dieses Pakets:** „Angebot machen"-Shortcut im Spielerprofil, Wechselsperre-Anzeige im Spielerprofil, Creator-Mode-Transferaufsicht (§ 9 der Spec).

## Reihenfolge-Empfehlung für die Umsetzung

1. Datenmodell + Migrationen (§ 13.3), Budget-Reservierungen (`ClubBudget.reserved`).
2. Reiter **Transfermarkt** (Listen, Filter, Gebotsverlauf, Deal-Sheet, Jugendabgabe-Berechnung).
3. Cronjob **Auktionsabschluss** + Historie-Einträge + Wechselsperre.
4. Reiter **Kader anbieten** (Statusboard, Auf-TL-stellen-Modal, 👁-Beobachter, Forum-Post).
5. Reiter **Meine Deals** + **Deal-Builder** (inkl. Zusammenfassungs-Popup).
6. Reiter **Leihmarkt** + laufende Leihen + Leistungs-Popup.
7. Reiter **Historie** (Paginierung, Tausch-Zeilen, Melden).
8. Push-Katalog (§ 8), Ticker + Gerüchte-Anbindung an die Vereinsnews.
9. Creator-Mode Transferaufsicht (§ 9).
