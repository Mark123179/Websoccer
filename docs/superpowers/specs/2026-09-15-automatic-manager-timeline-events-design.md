# Automatische Ereignisse in der Manager-Timeline

## Ziel

Objektiv aus dem Spielzustand ableitbare Karriereereignisse werden automatisch und dauerhaft in der Manager-Timeline gespeichert. Manuelle Einträge bleiben besonderen, subjektiv wichtigen Ergebnissen wie Derbysiegen oder Sensationen vorbehalten.

Alle bereits vorhandenen historischen Daten werden einmalig nachgetragen.

## Automatische Ereignisse

Bereits vorhandene automatische Amtsantritte und Vereinswechsel bleiben erhalten. Automatische Titel ohne Finalspiel, beispielsweise Meisterschaften und Aufstiege, behalten ihre normale Titelkarte.

Neu automatisch gespeichert werden:

1. Ausgetragene Finalspiele für beide beteiligten Manager
2. Rücktritte
3. Entlassungen
4. Einvernehmliche Trennungen
5. Amtszeitenden ohne genauer gespeicherten Grund

Urlaub, Inaktivitätsanzeige und andere allgemeine Statusmeldungen erzeugen keine zusätzlichen Timeline-Ereignisse.

## Datenmodell

Automatische Timeline-Einträge verwenden dieselbe darstellbare Ereignisschicht wie genehmigte manuelle Einträge. Sie erhalten zusätzlich:

- eine Kennzeichnung als systemseitiger Eintrag,
- einen stabilen Quellentyp,
- einen stabilen Quellschlüssel.

Die Kombination aus Quellentyp und Quellschlüssel ist eindeutig. Wiederholte Abschluss-, Saison- oder Backfill-Läufe dürfen deshalb keinen zweiten Eintrag für dasselbe Ereignis erzeugen.

Manuelle Einträge behalten Moderationsstatus und bestehenden Ablauf. Systemeinträge sind direkt sichtbar und benötigen keine Freigabe.

## Finalspiele

Nach dem verbindlichen Abschluss eines Finalspiels entsteht für jeden der beiden beteiligten Manager genau ein Ereignis. Beide Einträge verweisen auf dasselbe Spiel, besitzen aber managerbezogene Quellschlüssel.

Der Sieger erhält ein goldenes Panorama-Finalticket als Titelereignis. Der Verlierer erhält dasselbe Panorama-Finalticket in Rot mit der Bedeutung „Finale verloren“.

Für einen Finalsieger darf nicht zusätzlich eine separate goldene Titelkarte zum selben Wettbewerb und Datum in der Timeline erscheinen. Der zugrunde liegende persönliche Titel-Datensatz bleibt für Trophäen, Statistiken und Managererfolge erhalten; nur seine separate Darstellung in der Timeline wird unterdrückt, wenn ein passendes Finalticket existiert.

Titel ohne Finalspiel, insbesondere Meisterschaften und Aufstiege, bleiben unverändert als normale Titelkarten sichtbar.

Das Ereignis enthält:

- Spieldatum,
- Wettbewerb,
- beide Vereine,
- Endergebnis einschließlich einer möglichen Entscheidung nach Verlängerung oder Elfmeterschießen,
- den konkreten Finaltitel.

Es verwendet automatisch die bestehende Panorama-Ticketdarstellung mit den echten Vereinswappen und dem Original-Wettbewerbslogo.

Ein Finalereignis wird nur erzeugt, wenn der Verein zum Zeitpunkt des Finals einem Manager eindeutig zugeordnet werden kann. Spätere Managerwechsel verändern die historische Zuordnung nicht.

## Amtszeitenden

Jedes beendete Manageramt erzeugt genau ein Ereignis. Der gespeicherte Grund bestimmt den Titel:

- Rücktritt
- Entlassung
- Einvernehmliche Trennung
- Amtszeit beendet

Ein konkreter Trennungsgrund und das allgemeine Amtszeitende dürfen nicht als zwei separate Ereignisse erscheinen. Der allgemeine Titel ist ausschließlich der Fallback für Datensätze ohne genaueren Grund.

Das Ereignis enthält den betroffenen Verein und das Enddatum. Bereits vorhandene automatische Entlassungseinträge werden über ihre Quelle erkannt und nicht dupliziert.

## Historischer Backfill

Ein idempotenter Verwaltungsbefehl durchsucht:

- alle abgeschlossenen Finalspiele mit eindeutig ermittelbaren damaligen Managern,
- alle beendeten Manageramtszeiten.

Er legt fehlende Systemereignisse an und überspringt bereits vorhandene. Er verändert keine manuellen Einträge und keine bestehenden Karriere-, Titel- oder Matchdaten.

Bei historischen Finalsiegern erzeugt der Backfill das goldene Finalticket. Die bisher aus dem persönlichen Titel abgeleitete Timeline-Karte wird anschließend bei der Timeline-Zusammenstellung unterdrückt, statt den persönlichen Titel-Datensatz zu löschen.

Wenn historische Daten für eine eindeutige Managerzuordnung, einen Gegner oder ein Ergebnis nicht ausreichen, wird der Datensatz protokolliert und übersprungen statt geraten.

## Darstellung

- Finalspiele erscheinen als Ergebnis-Tickets: Gold für den Sieger, Rot für den Verlierer.
- Pro Manager und Finalspiel erscheint genau eine Karte.
- Eine separate Final-Titelkarte wird beim Sieger unterdrückt, sobald das zugehörige Finalticket vorhanden ist.
- Amtszeitenden erscheinen als normale Statuskarten.
- Manuelle Ergebnis-Tickets verwenden ohne Überschrift den neutralen Titel „SPIELERGEBNIS“.
- Automatische Finaltickets verwenden einen konkreten Finaltitel.
- Original-Logos werden über bestehende Vereins- und Wettbewerbs-Assetpfade geladen; erfundene Ersatzlogos sind nicht erlaubt.

## Tests und Abnahme

Die Tests prüfen:

- je ein Finalereignis für beide zum Spielzeitpunkt verantwortlichen Manager,
- genau eine sichtbare Karte pro Manager und Finale,
- goldenes Finalticket für den Sieger und rotes Finalticket für den Verlierer,
- Unterdrückung nur der doppelten Final-Titelkarte, ohne den persönlichen Titel-Datensatz zu löschen,
- unveränderte Titelkarten für Meisterschaften, Aufstiege und andere Titel ohne Finalspiel,
- korrekte Vereine, Wettbewerb, Ergebnis und Logo-Verknüpfungen,
- keine Duplikate bei wiederholtem Abschluss,
- jeden unterstützten Trennungsgrund,
- genau ein Ereignis pro Amtszeitende,
- Fallback „Amtszeit beendet“ bei fehlendem Grund,
- vollständigen und wiederholbaren historischen Backfill,
- Überspringen uneindeutiger historischer Daten,
- unveränderte manuelle Moderation und bestehende Timeline-Darstellung.