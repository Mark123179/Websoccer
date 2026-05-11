# Websoccer Design System

## Richtung

Das Websoccer-UI nutzt eine PlayStation-inspirierte Kapitelstruktur:

- dunkle Editorial-Bereiche fuer Verein, Identitaet und Fokusmomente
- helle Utility-Bereiche fuer Tabellen, Daten und Managerarbeit
- PlayStation Blue `#0070d1` als sparsamer Primaerakzent fuer CTAs, aktive Links und wichtige Trennlinien

Der Websoccer bleibt ein dichtes Managerprodukt, wird aber nicht mehr wie eine alte HTML-Tabelle gestaltet. Inhalte bleiben kompakt, scanbar und datenstark.

## Tokens

- `--ps-blue`: `#0070d1`
- `--ps-blue-pressed`: `#0064b7`
- `--canvas-dark`: `#000000`
- `--surface-dark`: `#121314`
- `--surface-dark-card`: `#181818`
- `--canvas-light`: `#ffffff`
- `--surface-soft`: `#f3f3f3`
- `--surface-card`: `#f5f7fa`
- `--ink`: `#000000`
- `--body-light`: `rgba(0,0,0,0.64)`
- `--on-dark`: `#ffffff`
- `--body-dark`: `rgba(255,255,255,0.72)`
- `--radius-card`: `8px`
- `--radius-pill`: `9999px`
- `--section-space`: `64px`

## Komponenten

- Hauptnavigation: dunkle Leiste, klare Links, keine dekorativen Verlaeufe.
- Club-Hero: dunkles Kapitel mit grossem Wappen, Clubname in leichter Display-Typografie, Links als blaue/outline Pills.
- Informationsbereich: heller Utility-Bereich mit 8px-Datenpanels.
- Auffaellige Spieler: helle Cards mit Spielerbild, Label und Kernwert.
- Trikots: helle Card-Gruppe, grosse freigestellte Kits.
- Kader: kompakte Tabelle auf hellem Canvas mit klaren Zeilen, groesseren Bildern und ruhigen Grenzen.

## Regeln

- Keine alten grauen Verlaufslabellen als Primaerstil.
- Keine blau dominierte Seite: Blau ist Akzent, nicht Flaechenfueller.
- Keine verschachtelten Cards.
- Tabellen bleiben dicht, aber mit lesbarer Zeilenhoehe und klaren Touch-/Click-Zielen.
- Spieler-, Wappen-, Flaggen- und Kit-Assets bleiben lokal und werden ueber IDs zugeordnet.
