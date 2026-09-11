# Implementierungsplan: Community-Turniere

**Grundlage:** `docs/superpowers/specs/2026-09-11-community-turniere-freundschaftsspiele-design.md`

## 1. Datenmodell und Migration

- Turnier, Teilnahme, Bewerbung, Runde, Paarung und Tabelle modellieren.
- Datenbank-Constraints für eindeutige Teilnahme, Paarungsfortschritt und Prämienzustand ergänzen.
- Turnierpartien eindeutig mit `FriendlyFixture` verbinden.
- Migration auf dem aktuellen Stand nach `0174` erzeugen.

## 2. Turnier-Service

- Erstellen, Beitritt, Codezugang, Bewerbung und Teilnehmerverwaltung transaktional implementieren.
- Formatvalidierung und vollständigen Terminplan erzwingen.
- Manuelles Starten mit ausgewählten KI-Vereinen, Feldverkleinerung und Pokal-Freilosen implementieren.
- Zufallsauslosung ohne Stärke, Liga-Spielplan und Gruppenverteilung erzeugen.
- Turnierpartien über den bestehenden Friendly-Sandkasten ansetzen.
- Tabellen, K.-o.-Fortschritt, Nichtantritt und Vereinsausfälle deterministisch und idempotent verarbeiten.
- Systemprämien ausschließlich für Admins, unveränderlich ab dem ersten gespielten Spiel und idempotent über das Ledger auszahlen.
- Postfachbenachrichtigungen außerhalb kritischer Transaktionen versenden.
- Saison- und 14-Tage-Bereinigung ergänzen.

## 3. Tick und HTTP

- Den bestehenden Friendly-Tick um den idempotenten Turnierfortschritt ergänzen.
- Eigene namespaced Turnieraktionen mit Login-, Vereins-, Rollen-, Zustands- und CSRF-Prüfung bereitstellen.
- Übersicht, Wizard, Detailseite, Bewerbungsverwaltung, Start-Pop-up und Terminänderung anbinden.

## 4. Oberfläche

- Turnierreiter gemäß Referenz als dreispaltige Kartenübersicht umsetzen.
- Vierstufigen Inline-Wizard oberhalb der sichtbaren Karten bauen.
- Spielplanzeilen, Zugangszustände, KI-Auswahl und read-only Admin-Prämienschritt umsetzen.
- Turnierdetail mit Teilnehmern, Spielplan, Tabelle beziehungsweise Gruppen und K.-o.-Baum ergänzen.
- Vorhandene Design-Tokens nutzen und Styles auf den Friendly-Bereich kapseln.
- 1440×900 als Golden Master und schmale Ansichten ohne horizontales Überlaufen sicherstellen.

## 5. Verifikation

- Modell- und Service-Tests für alle Formate, Zugänge, Parallelität, Auslosung, Wertung, Freilose, Nichtantritt, Prämien und Bereinigung ergänzen.
- HTTP- und Template-Verträge testen.
- Fokussierte Django-Tests, Migration-Check und System-Check ausführen.
- Workflow einmal nach dem vollständigen Änderungsblock neu starten und Logs prüfen.
- Finale 1440×900-Aufnahme sowie eine schmale Darstellung kontrollieren.
