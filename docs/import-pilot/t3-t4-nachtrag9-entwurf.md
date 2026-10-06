# T3 und T4: technischer Entwurf mit Nachtrag 9

Stand: 06.10.2026. Fachlicher Umfang: Nachträge 8 und 9; Nachtrag 9 hat Vorrang.

## Grenzen

Der Pilot bleibt fachlich auf BVB-Paket v1. v2 wird ausschließlich in einer
eigenen Testdatenbank angewendet, bis Mark es selbst im Creator bestätigt.
Keine Stärkeformeländerung, kein Reset/T5, keine Dortmund-Szenensicherung,
kein Hetznerzugriff und keine Veröffentlichung.
Gemeinsame additive Schemaänderungen folgen der bereits bestätigten
Migrationsregel. Der bestehende Verhaltensschalter schützt den Altmodus.

## Architektur und Alternativen

Empfohlen: vorhandene ImportIssue-Arbeitsliste erweitern. Eine zweite
Arbeitsliste neben den vorhandenen Zeilen würde zwei Wahrheiten schaffen
und erledigte Einträge vom bisherigen Verlauf trennen; sie wird verworfen.

Fokussierte Dienste für Arbeitslistenabgleich, Paketvergleich und
Handnachpflege ergänzen den bestehenden Paketimport. Die Creator-Oberfläche
benutzt diese Dienste; sie implementiert keine eigene Import- oder
Stärkeberechnung. T4 passt die vorhandenen Seiten an, statt Parallelseiten
mit kopierter Fachlogik aufzubauen.

## Arbeitsliste

Eindeutiger Schlüssel: Verein, Gegenstandsart, Gegenstandsbezug und Feld.
Text, Schwere und Upload gehören nicht zum Schlüssel. Der ursprüngliche
Upload bleibt nachlesbar; der zuletzt bestätigende Upload wird erfasst.
Der eindeutige Schlüssel wird in der Datenbank abgesichert.

Alle Eintragsarten werden im Abgleich berücksichtigt: Paketlücken,
externe Vereinsverweise, Verknüpfungsvorschläge, Prüfpool und Bildprüfung.
Bestehende Zeilen werden vor Einführung der Eindeutigkeit konsistent
zugeordnet; bereits erledigte Einträge dürfen nicht still verloren gehen.

- Gleiche Lücke: dieselbe Zeile; Status erhalten, Text und Schwere aktualisieren.
- Fehlende Lücke: offene Zeile als durch Paket erledigt schließen.
- Neue Lücke: neue offene Zeile.
- Wiederkehr: vom Paket geschlossene Zeile wieder öffnen; handerledigte
  Zeile bleibt erledigt, solange der Handeintrag nach N44 erhalten bleibt.
- Einzelsperren sind nicht von Hand abhakbar.

Handabschluss und Paketabschluss bleiben unterscheidbar. Derselbe Upload
darf keine Doppelzeilen erzeugen.

## Handeinträge und Identitäten

Handeinträge füllen fehlende Werte. Fehlender Paketwert erhält den
Handeintrag und dessen Status. Gleicher Paketwert übernimmt den Status
gefunden ohne Konfliktanzeige. Abweichender Paketwert hat Vorrang und wird
mit Alt-/Neuwert vor Bestätigung angezeigt.

Dies gilt für externe IDs, externe Vereinsverweise, bestätigte
Verknüpfungen und Prüfpool-Zuordnungen. Identitätskonflikte führen nicht
zum automatischen Zusammenführen oder Umidentifizieren, sondern auf die
Arbeitsliste. Nach Ligastart gilt weiterhin die bestätigte Schreibmaske.

Die Einzelsperre wird nach Import und Nachpflege aus dem Datenstand
abgeleitet: benötigte Quellwerte und eine berechnete Stärke müssen
vorhanden sein. Eine neue ID ohne Rating genügt nicht.

## T3: Oberfläche und Sicherheit

Creator-Upload: Prüfung, schreibfreie Vorschau, Zielliga, Bestätigung.
Die Vorschau zeigt Mannschaftszahlen, Leihen, Schwere der Lücken,
fehlende Bilder, geänderte Werte und Handeinträge, Prüfpool sowie eine
Bilanz neuer, bleibender und geschlossener Arbeitslisteneinträge.
Vor der Bestätigung werden Zustand und Berechtigung erneut geprüft;
Bestätigung und Abgleich erfolgen als eine atomare Einheit.

Upload-/Vorschau-Zustand darf keine dauerhaften fachlichen Zeilen
erzeugen. Abbruch hinterlässt keine Importdaten. Dateibehandlung folgt
dem bestehenden Projektmuster und darf Paketinhalt nicht ungeprüft
entpacken. Creator-Berechtigung, CSRF und Liga-/Vereinszuordnung werden
serverseitig geprüft.

Liga-Anlage mit spielbar/nicht spielbar; Arbeitsliste nach Liga, Verein
und Schwere; Nachpflege und Bestätigungsvorschläge aus dieser Liste.
Offene sperrende Einträge verhindern Ligastart in sämtlichen Startwegen.
Bildprüfung liest erwartete Dateien unter ASSETS_ROOT; keine Bild-Uploads.

## T4: bestehende Seiten und Pilotzugang

Vereinsseite mit Stammdaten, Farben, Spitzname, Motto und zwölf
Stadionkapazitäten. Kader mit erster Mannschaft, Rückennummern,
Positionen, Leihkennzeichnung und getrenntem Leih-Pool.
U21 ist nur im Creator sichtbar und nicht aufstellbar.

Spielerprofil mit vollständigem Marktwertgraph, gekennzeichnetem
Startwert und neuester Transferzeile oben. Fremde Vereine bleiben
externe Referenzen mit Name und leerem Wappen. Unbekannt ist nicht null
im Sinne einer angezeigten Zahl 0.

Ruhmeshalle mit echten Rekorden und Titeln; Titelzählung aus den
Einzeleinträgen. Neue Rekordschlüssel speichern, aber nicht ungefragt
anzeigen. Fehlende Wappen dürfen keinen Serverfehler auslösen.

Pilotzugang unter eigener Adresse im Projekt mit normalem Nutzerkonto.
Nur die freigegebenen Creator-Schreibwege werden geöffnet.
Hintergrundjobs bleiben deaktiviert.

## Verifikation und Bericht

Vor den Änderungen Ausgangsbelege des Pilots sichern, ohne Secrets oder
personenbezogene Kontodaten zu exportieren. Separater Testbestand mit
dem gemeinsamen Schema und der echten Import-/Stärkepipeline.

| Größe | v1 | v2 |
|---|---:|---:|
| Spieler | 51 | 51 |
| Berechnete Stärke | 35 | 49 |
| Einzelsperren | 2 | 2 |
| Quellstand-Archiv | 83 | 132 |
| Marktwertpunkte | 637 | 637 |
| Transfers | 322 | 322 |
| Rekorde | 24 | 24 |
| Titel-Einzeleinträge | 30 | 30 |
| Arbeitslistenzeilen | 156 | 156 |
| Offen | 156 | 128 |
| Durch Paket erledigt | 0 | 28 |
| Club-Zeilen | 1 | 1 |

Stichproben Basis/Potenzial: Nwaneri 145/181, Inácio 120/166,
Reggiani 116/152, Fahrenhorst 90/160, Wüstenhagen 92/100.
Dritter Import v2 muss sämtliche Zeilen unverändert lassen, nicht nur
die Anzahlen. Abweichende Werte mit Ursache berichten; keine Anpassung
der Stärkeformel, um Sollzahlen zu erzwingen.

Zusätzlich gezielt prüfen: Wiederkehr einer Lücke, Erhalt handerledigter
Einträge, gleiche/abweichende/fehlende Paketwerte, Identitätskonflikte,
datenabhängige Einzelsperren und Rechte-/CSRF-Grenzen.

Der Abschlussbericht enthält alle zehn Punkte:
1. Pilotadresse und Anmeldung.
2. Upload, Vorschau, Bestätigung und Arbeitsliste mit Bildschirmfotos.
3. Nachweis schreibfreier Vorschau und rückstandsfreien Abbruchs.
4. Sämtliche geprüften Ligastartwege und Sperren.
5. Fehlende Bilder beim BVB nach Art.
6. Bildschirmfotos der vier bestehenden Seiten.
7. Neue Stellen mit Verhaltensschalter.
8. Altmodus-Testergebnis.
9. Gemessene v1/v2-Werte, fünf Stichproben, Nachweis Pilot weiterhin v1.
10. Arbeitslistenschlüssel, Wiederkehrverhalten, Vorschau mit Bilanz.

Nach T3 und T4 Halt. Kein automatischer v2-Import im Pilot.
