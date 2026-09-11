# Community-Turniere für Freundschaftsspiele

**Datum:** 11.09.2026  
**Status:** Vom Nutzer fachlich und visuell freigegebener Entwurf; schriftliche Abschlussprüfung ausstehend  
**Aufgabe:** #932 „Community-Turniere für Freundschaftsspiele“

## 1. Ziel und Abgrenzung

Manager können Community-Turniere im bestehenden Bereich „Freundschaftsspiele“ erstellen und durchführen. Unterstützt werden Liga, Pokal sowie Gruppenphase mit anschließender K.-o.-Phase. Turnierpartien verwenden den vorhandenen Friendly-Sandkasten für Termin, Simulation und Spielbericht.

Turnierspiele bleiben vollständig von Pflichtspielwirkungen isoliert:

- keine persistierten Änderungen an Frische, Verletzungen, Karten, Sperren oder Form
- keine Pflichtspiel- oder Saisonstatistiken
- keine Spieltagseinnahmen oder sonstigen automatischen Finanzbuchungen
- eigener Taktikkontext `freundschaft`
- keine Heimvorteile bei neutralem Spielort
- keine Anzeige im globalen Kalender

„Kalendereinbindung“ bezeichnet ausschließlich den turniereigenen Spielplan und die Berücksichtigung aller Spiele bei Kollisionsprüfungen.

## 2. Architekturentscheidung

Die Turnierverwaltung bildet eine eigenständige Domäne oberhalb des vorhandenen Friendly-Systems. Turnier, Teilnahme, Bewerbung, Phase, Runde, Tabelle und Paarung sind eigene persistierte Objekte. Jede tatsächlich angesetzte Turnierpartie verweist für Termin, Simulation und Bericht auf genau ein normales `FriendlyFixture`.

Der bestehende Friendly-Tick simuliert die Partie. Ein separater, idempotenter Turnier-Fortschreiber verarbeitet anschließend Ergebnis, Tabelle und Baum.

Diese Trennung verhindert, dass:

- Einzel-Friendlies mit Turnierzuständen überladen werden,
- der bestehende DFB-Pokal oder Pflichtspielstatistiken verändert werden,
- der bewährte Friendly-Sandkasten dupliziert wird.

## 3. Domänenmodell

### 3.1 Community-Turnier

Ein Turnier enthält mindestens:

- Name und Beschreibung
- Saison
- Mannschaftskontext `pro` oder später `u21`
- Format `liga`, `pokal` oder `gruppen_ko`
- feste Feldgröße
- Ligaoption einfache Runde oder Hin- und Rückrunde
- Pokaloption Einzelspiel oder Hin- und Rückspiel
- Zugang `offen`, `code` oder `bewerbung`
- optionalen Einladungscode
- turnierweiten Regelsatz
- turnierweiten Spielort einschließlich neutraler Austragung
- Veranstalterverein
- Status und Zeitstempel
- optionalen Admin-Prämienplan

Der Veranstalterverein liegt direkt am Turnier. Der Veranstalter muss nicht teilnehmen.

### 3.2 Teilnahme

Eine Teilnahme repräsentiert nur eine tatsächlich mitspielende Mannschaft:

- Turnier und Verein sind gemeinsam eindeutig.
- Eine Teilnahme kennzeichnet Manager- oder KI-Verein.
- Gruppenkennung und gespeicherte Losposition sind optional.
- Aufnahme und letzter freier Platz werden transaktional geschützt.

### 3.3 Bewerbung

Für Turniere mit Bewerbungszugang gibt es Bewerbungen mit den Zuständen offen, angenommen, abgelehnt und zurückgezogen. Eine Annahme erzeugt atomar eine Teilnahme, sofern noch Platz besteht.

### 3.4 Phasen, Runden und Paarungen

- Liga verwendet Spieltage.
- Pokal verwendet K.-o.-Runden.
- Das Kombiformat verwendet Gruppenphase und anschließende K.-o.-Runden.
- Alle Runden- und Spieltagstermine werden vor Öffnung der Anmeldung vollständig festgelegt.
- Eine Turnierpaarung verweist auf ihr `FriendlyFixture` sowie eindeutig auf ihre Vorgängerzweige.

### 3.5 Tabelle

Liga- und Gruppentabellen speichern:

- Spiele
- Siege, Unentschieden und Niederlagen
- Tore und Gegentore
- Punkte
- Gruppenkennung, falls vorhanden

Jede Partie darf höchstens einmal eingerechnet werden.

## 4. Lebenszyklus

1. Der Veranstalter erstellt das Turnier im vierstufigen Wizard.
2. Der Wizard verlangt einen vollständigen und grundsätzlich konfliktfrei planbaren Terminplan.
3. Das Turnier wird zur Anmeldung geöffnet; Interessenten sehen Termine und Regeln vor ihrem Beitritt.
4. Vereine treten offen oder per Code bei beziehungsweise bewerben sich.
5. Der Veranstalter startet das Turnier manuell.
6. Bei unvollem Feld öffnet sich ein Auswahl-Pop-up mit geeigneten KI-Vereinen. Der Veranstalter wählt Auffüller selbst oder verkleinert das Feld; beim Pokal sind alternativ Freilose möglich.
7. Der Start speichert Teilnehmer-Snapshot und Auslosung und bindet die Paarungen an den bereits vorhandenen Terminplan.
8. Der Friendly-Tick simuliert fällige Partien.
9. Der Turnier-Fortschreiber aktualisiert Tabellen und erzeugt Folgepaarungen.
10. Nach dem letzten Spiel wird das Turnier abgeschlossen.
11. Konfigurierte Systemprämien werden genau einmal über das Finanz-Ledger ausgezahlt.
12. Abgeschlossene Turniere und Berichte bleiben bis zum Saisonwechsel erhalten und werden dann mit den saisongebundenen Friendly-Daten atomar gelöscht.

Nicht gestartete, verwaiste Turniere werden nach 14 Tagen bereinigt. Dies ist die einzige 14-Tage-Regel.

## 5. KI-Auffüllung

KI-Vereine sind vollwertige Turnierteilnehmer.

- Es gibt keine automatische, unsichtbare Auswahl.
- Das Start-Pop-up zeigt alle geeigneten KI-Vereine.
- Der Veranstalter wählt die Auffüller selbst.
- Ein KI-Verein darf nicht bereits teilnehmen und keine Terminkollision besitzen.
- Alternativ kann der Veranstalter auf eine zulässige Feldgröße verkleinern.
- Bei einem Pokalturnier können freie Positionen in Runde 1 als Freilose behandelt werden.

## 6. Formate und Feldgrößen

### 6.1 Liga

- 4, 6, 8, 10 oder 16 Mannschaften
- einfache Runde oder Hin- und Rückrunde
- `(n - 1)` beziehungsweise `2 × (n - 1)` Spieltage

### 6.2 Pokal

- 4, 8 oder 16 Mannschaften
- Einzelspiele oder Hin- und Rückspiele
- keine Auswärtstorregel
- auslosungsbedingte Freilose nur in Runde 1
- ausfallbedingte Freilose in jeder Runde möglich

### 6.3 Gruppenphase plus K.-o.

- 8 Mannschaften: 2 Gruppen mit je 4 Mannschaften
- 16 Mannschaften: 4 Gruppen mit je 4 Mannschaften
- genau 3 Gruppenspieltage
- die beiden Erstplatzierten jeder Gruppe erreichen die K.-o.-Phase
- bei 8 Teilnehmern folgt das Halbfinale
- bei 16 Teilnehmern folgt das Viertelfinale

## 7. Auslosung und Heimrecht

- Es gibt keine Setzliste und keine Verwendung geheimer Mannschaftsstärken.
- Beim reinen Pokal wird der vollständige Baum beim Start zufällig ausgelost.
- Beim Kombiformat werden beim Start nur die Gruppen ausgelost.
- Die K.-o.-Endrunde wird nach Abschluss der Gruppenphase zufällig ausgelost.
- Lospositionen werden dauerhaft gespeichert und nicht neu berechnet.
- Pokal-Heimrecht wird bei Einzelspielen ausgelost.
- Bei Hin- und Rückspielen wird das Heimrecht getauscht.
- In der Liga folgt das Heimrecht dem Rundenspielplan.
- Neutraler Spielort gilt als Turniereinstellung für alle Partien.

## 8. Wertung und Entscheidungsregeln

### 8.1 Tabellenreihenfolge

Bei Punktgleichheit entscheidet:

1. Tordifferenz
2. erzielte Tore
3. direkter Vergleich, soweit eindeutig anwendbar
4. dauerhaft gespeichertes Zufallslos

Das gespeicherte Los hält die Reihenfolge über wiederholte Tick-Läufe stabil.

### 8.2 K.-o.-Entscheidung

Der Wizard lässt Pokal- oder K.-o.-Turniere nur mit einem entscheidungsfähigen Regelsatz zu.

- Einzelspiele werden bei Gleichstand gemäß Regelsatz durch Verlängerung und/oder Elfmeterschießen entschieden.
- Bei Hin- und Rückspielen zählt das Gesamtergebnis.
- Bei Gleichstand nach dem Rückspiel folgen Verlängerung beziehungsweise Elfmeterschießen.
- Es gibt keine Auswärtstorregel.
- Freilose erzeugen keine simulierte Partie.

### 8.3 Nichtantritt und Ausfall

Ist genau eine Mannschaft beim Anpfiff nicht spielfähig:

- Die Partie wird als „nicht ausgetragen“ protokolliert.
- Die spielfähige Mannschaft gewinnt die Turnierwertung.
- In K.-o. zieht sie weiter.
- In Liga oder Gruppe erhält sie die festgelegte Siegwertung.

Sind beide Mannschaften nicht spielfähig:

- Die Partie wird als „nicht ausgetragen“ protokolliert.
- Liga oder Gruppe: 0:0 und keine Punkte für beide.
- K.-o.: Beide scheiden aus; die spätere Paarung im anderen Zweig wird zum Freilos.
- Das Turnier läuft ohne manuellen Eingriff weiter.

Wird ein Verein gelöscht:

- Offene Liga- und Gruppenspiele werden regelkonform als nicht ausgetragen gewertet.
- In K.-o. erhält die vorhandene Gegenseite ein ausfallbedingtes Freilos.
- Der Baum wird nicht neu ausgelost.

Verlässt ein Manager seinen Verein, bleiben Teilnahme und Spiele beim Verein. Fällt der Veranstalter aus, laufen Terminplan und Fortschreibung weiter.

## 9. Terminplanung und Kollisionen

Der Veranstalter terminiert sämtliche Spieltage und Runden im Wizard vorab. Der Turnierstart verwendet diesen Plan und erzeugt ihn nicht neu.

- Regulär terminierte Spiele blockieren ein Drei-Stunden-Fenster.
- Geprüft werden Pflichtspiele, Friendlies und Community-Turnierpartien im gleichen Mannschaftskontext.
- Pflichtspiele ohne Uhrzeit und Pokalrunden blockieren als sicherer Fallback den ganzen Tag.
- Der Wizard benennt unbrauchbare Termine und den verursachenden Konflikt.
- Termine dürfen bis zum jeweiligen Anpfiff verschoben werden.
- Jede Verschiebung wird erneut auf Kollisionen geprüft.
- Betroffene Teilnehmer werden über Verschiebungen benachrichtigt.

## 10. Systemprämien

Turnierprämien sind optionale Systemprämien und dürfen neues Geld erzeugen.

- Nur Admins dürfen Prämien setzen oder verändern.
- Die Berechtigung wird serverseitig geprüft.
- Änderungen sind nur erlaubt, solange noch keine Turnierpartie gespielt wurde.
- Ab dem ersten gespielten Spiel ist der Prämienplan unveränderlich.
- Unterstützte Verteilungen sind „Nur der Sieger“, „Top 3 (50/30/20)“ und eine eigene Verteilung.
- Eine eigene Verteilung muss vollständig und konsistent sein.
- Nach Turnierende werden Prämien idempotent über die verbindliche Ledger-Schnittstelle gebucht.
- Ohne Adminberechtigung ist der Wizard-Schritt nur lesbar und verhindert die Turniererstellung nicht.

## 11. Rechte und Parallelität

- Jeder Manager mit Verein darf ohne Mengenlimit Turniere erstellen.
- Der Veranstalter darf Bewerbungen verwalten und Teilnehmer vor dem Start entfernen.
- Nach dem Start ist das Teilnehmerfeld unveränderlich, abgesehen von deterministischen Ausfällen.
- Zugangscodes werden nicht in Listen oder Benachrichtigungen offengelegt.
- Codes können vor dem Start durch den Veranstalter ersetzt werden.
- Alle mutierenden Endpunkte prüfen Login, Vereinsbezug, Rolle, Zustand und CSRF.
- Beitritt, Bewerbungsannahme, Start und letzte freie Plätze verwenden Transaktionen und Zeilensperren.
- Auslosung, Ergebnisfortschreibung und Prämienauszahlung sind idempotent.
- Benachrichtigungen laufen außerhalb kritischer Transaktionen und dürfen keinen Fachvorgang zurückrollen.

## 12. Benachrichtigungen

Das vorhandene Postfach informiert gezielt über:

- neue Bewerbung
- Annahme oder Ablehnung einer Bewerbung
- erfolgreichen Beitritt
- Entfernung vor Turnierstart
- Turnierstart und erste Paarung
- Terminverschiebung
- neu feststehende K.-o.-Paarung
- Turnierabschluss und Platzierung
- ausgezahlte Systemprämie

Automatische KI-Aktionen erzeugen keine unnötigen Managerbenachrichtigungen.

## 13. Oberfläche

### 13.1 Gemeinsamer Friendly-Desk

Die fünf Reiter bleiben:

1. Spiel ansetzen
2. Spielbörse
3. Offene Anfragen · Anzahl
4. Turniere
5. Historie

Oben rechts bleiben der Umschalter Profis/U21 und „Mein Verein“. Der Turnierbereich erhält keine eigene Sidebar und keine separate Hauptnavigation.

### 13.2 Turnierübersicht

Unter der Reiterleiste stehen:

- „Community-Turniere — als Liga, Pokal oder Gruppenphase + K.o.“
- rechts der Button „Turnier erstellen“
- darunter auf breiten Screens ein dreispaltiges Kartenraster

Eine Karte zeigt:

- Turniername
- Format-Badge
- Teilnehmerstand
- Startdatum
- Ersteller
- Zugangsart
- optionale orange Prämienplakette
- zustandsabhängige Aktionen

Aktionen und Zustände umfassen „Angemeldet“, „Zum Turnier“, „Beitreten“, „Code eingeben“ und die Bewerbungsaktion.

### 13.3 Inline-Wizard

„Turnier erstellen“ blendet oberhalb der Karten ein breites Panel „Neues Turnier erstellen“ ein. Die Karten bleiben darunter sichtbar.

Die Schritte lauten exakt:

1. Format
2. Teilnehmer & Zugang
3. Spielplan
4. Prämie (Admin)

Unten links steht „Abbrechen“, unten rechts stehen „Zurück“ und „Weiter“ beziehungsweise „Turnier erstellen“. Der Wizard ist weder Vollbilddialog noch eigene Seite.

### 13.4 Schritt 1 – Format

Drei Auswahlkarten:

- Liga — „Jeder gegen jeden — Tabelle entscheidet“
- Pokal — „K.o.-Modus mit Auslosung“
- Gruppen + K.o. — „Gruppenphase, dann K.o.-Baum“

Die aktive Auswahl hat Cyan-Rahmen und Cyan-Akzent. Darunter erscheinen nur formatabhängige Optionen.

### 13.5 Schritt 2 – Teilnehmer und Zugang

Der Schritt zeigt:

- verbindliche Feldgrößen
- Zugang offen, Einladung oder Bewerbung
- bei Einladung das Codefeld
- Erklärung der Möglichkeiten bei unvollem Startfeld

Der Veranstalter wird nicht automatisch als Teilnehmer eingetragen.

### 13.6 Schritt 3 – Spielplan

- Hinweis auf die vollständige Vorab-Terminierung
- Cyan-Zusammenfassung der Rundenzahl
- scrollbare Zeilenliste innerhalb des Panels
- je Zeile Rundenname, Datum und Uhrzeit
- direkte Konfliktanzeige an der betroffenen Zeile
- optionaler Takt-Helfer zur Vorbelegung

### 13.7 Schritt 4 – Prämie (Admin)

Für Admins:

- „Prämie gesamt (Admin)“
- Auszahlungsvorschau
- Verteilungsoptionen
- konkrete Beträge
- Hinweis auf die Sperre ab dem ersten gespielten Spiel

Für Nicht-Admins:

- Schritt bleibt sichtbar
- bestehende Prämie wird read-only gezeigt
- ohne Prämie erscheint ein neutraler Hinweis
- Turniererstellung bleibt möglich

### 13.8 Turnierdetail

Die Detailansicht folgt der vorhandenen Standalone-Vorlage und derselben Panelsprache. Sie enthält:

- Teilnehmer und Bewerbungen
- Spielplan
- Liga- oder Gruppentabellen
- Pokal- beziehungsweise K.-o.-Baum
- Ergebnisse und Links zum bestehenden Spielbericht
- zulässige Veranstalteraktionen
- Admin-Prämienstatus

Die gelieferte Screenshotserie definiert keine neue Detailansicht. Nicht gezeigte Zustände werden mit vorhandenen Websoccer-Komponenten umgesetzt, nicht mit einer neuen Designsprache.

## 14. Visuelle Regeln und Responsive-Verhalten

- Django-Templates und bestehende Design-Tokens; kein React und kein zusätzlicher Build-Schritt
- Layout, Reihenfolge, Farben und Texte gemäß Standalone-Vorlage und gelieferten Screenshots
- 1440 × 900 ist die verbindliche Referenz
- drei Turnierkarten pro Reihe auf breiten Screens
- Umbruch ohne horizontales Überlaufen auf schmaleren Screens
- Cyan für Funktionen und aktive Zustände
- Grün für positive Zustände
- Orange ausschließlich für Prämien
- keine hellen Flächen, konkurrierende Designlogik oder unnötig verschachtelten Karten
- neue Styles bleiben auf den Friendly-/Turnierbereich gekapselt

## 15. U21

Das Datenmodell unterstützt `u21`, aber der echte Jugendkader gehört nicht zu dieser Aufgabe. Bis zum Jugendmodul zeigt der U21-Modus ausschließlich:

> Die U21 hat noch keinen Kader — der Jugendspielbetrieb ist in Arbeit.

Es werden keine Profi-Spieler als U21-Ersatz verwendet.

## 16. Abnahmekriterien

Die Umsetzung ist fachlich vollständig, wenn:

- alle drei Formate mit den festgelegten Feldgrößen erstellt werden können,
- der vollständige Terminplan vor der Anmeldung sichtbar ist,
- offene, Code- und Bewerbungszugänge parallelitätssicher funktionieren,
- der Veranstalter nicht teilnehmen muss,
- ein unvolles Feld über die explizite KI-Auswahl, Feldverkleinerung oder Pokal-Freilose gestartet werden kann,
- Auslosung, Tabelle, Baum und Folgepaarungen idempotent fortgeschrieben werden,
- kein Nichtantritt oder Vereinsausfall das Turnier blockiert,
- jede Partie im Friendly-Sandkasten ohne Pflichtspiel- oder Finanznebenwirkungen läuft,
- globale Kalenderanzeige und turniereigener Spielplan klar getrennt bleiben,
- Prämien nur durch Admins und nur bis zum ersten gespielten Spiel änderbar sind,
- Prämien genau einmal über das Ledger ausgezahlt werden,
- Benachrichtigungsfehler Fachvorgänge nicht zurückrollen,
- Saison- und Verwaisungsbereinigung den festgelegten Regeln folgen,
- die UI bei 1440 × 900 der Referenz entspricht und schmalere Ansichten nicht überlaufen.
