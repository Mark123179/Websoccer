# Import-Neuaufbau: Nachtrag 2 zur Übergabe

Stand: 05.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md`, Nachtrag 1 und zum T0-Bericht (`.local/tasks/t0-import-neuaufbau-bericht.md`)

Dieser Nachtrag beantwortet die offenen Fragen B1 bis B8 aus Abschnitt 10 des T0-Berichts und die zwei offenen Punkte aus Nachtrag 1. Er ergänzt Teil B der Übergabe und hat bei Widersprüchen Vorrang vor Teil A, Teil C und Nachtrag 1. Am BVB-Referenzpaket ändert er nichts.

Alle Entscheidungen hat Mark am 05.10.2026 einzeln getroffen.

## Entscheidungen

| # | Zu | Entscheidung |
|---|---|---|
| N5 | B1 | **Der Pilot läuft in einem zweiten Schema in derselben Datenbank**, nicht in einer eigenen Datenbank. Replits Empfehlung (eigene Datenbank) wurde vorgelegt und nicht gewählt |
| N6 | B2 | **Von den Benutzerkonten kommen nur Konto und Profil mit:** Login, Rollen und Gruppen, Managername, Profilbild, Einstellungen. Karriere-Stationen, Timeline, Mannschaftsfotos, persönliche Titel, XP, Level und Saison-Score starten bei null. Vereinsbindung leer. Gilt für den Pilot und später für den Live-Reset |
| N7 | B4 | **Regeln und Parameter werden 1:1 kopiert** und sind ein eigener Schutzbereich. Gemeint sind Tabellen ohne Vereins- oder Spielerbezug: Wirtschaftsparameter, Scouting-Länderkatalog, globales Stadionumfeld-Layout und vergleichbare Kataloge. Replit legt die Tabellenliste vor, Mark bestätigt sie, erst dann wird kopiert. Beim Live-Reset bleiben diese Tabellen stehen |
| N8 | B3 | **Das Forum ist kein Schutzbereich mehr.** Es gibt keine Forum-App und keine Forum-Tabellen, und `playwebsoccer.de/forum/` liefert „Not Found" (geprüft am 05.10.2026). Als Sicherung bricht der Reset-Befehl ab, sobald er eine Tabelle findet, die weder „löschen" noch „schützen" zugeordnet ist |
| N9 | B5 | **Gesetzte U21-Spieler bleiben immer im Kader.** Der Schlüssel 2-6-7-5 gilt nur fürs Auffüllen bis 20. Besetzen Gesetzte eine Gruppe über ihren Anteil, wird der Überhang bei den Auffüllern abgezogen: zuerst Mittelfeld, dann Abwehr, dann Angriff. Zwei Torhüter bleiben immer. Bei mehr als 20 Gesetzten wird nicht aufgefüllt, und der Startkader ist größer als 20 |
| N10 | B6 | **Spieler ohne Transfermarkt-Marktwert starten mit 50.000 €.** Ausdrückliche Ausnahme von „NULL bleibt NULL" (A2 Punkt 5), nur für diesen Fall. Der Server setzt den Wert beim Import, im Paket bleibt der TM-Wert leer. Details unten |
| N11 | B7 | **Vereinsverweise ohne TM-ID werden mit ihrem Originalnamen gespeichert**, unverknüpft und mit leerem Wappen. Je Name entsteht ein Info-Eintrag auf der Arbeitsliste (BVB: 13 Namen für 78 Einträge). Mark trägt dort die TM-ID nach, dann wird verknüpft. Kein Abgleich über den Namen. Künftige Pakete müssen die TM-ID mitliefern |
| N12 | B7 | **Die Arbeitsliste macht Verknüpfungsvorschläge.** Passt ein unverknüpfter Name zu einem vorhandenen Verein, zeigt sie den Vorschlag an. Verknüpft wird erst nach Marks Klick, nie automatisch |
| N13 | B8 | **Zur Kadergrenze zählt ein Spieler dort, wo er spielt**, wie bisher. Geliehene zählen beim Leihverein. Verliehene im Leih-Pool zählen nicht beim Stammverein. Liegt der Kader nach einer Rückkehr über der Grenze, sind Käufe gesperrt, bis wieder Platz ist. BVB zählt damit 47 |

## Was aus den Entscheidungen folgt

**Zu N5 (zweites Schema).** Die Trennung muss nachgewiesen sein, bevor im Pilot-Schema etwas geschrieben wird:

- eigener Suchpfad, eigener Migrationsstand, eigene Sitzungen und eigener Cache-Namensraum
- kein Hintergrundjob und kein Zeitplaner des bestehenden Systems schreibt in das Pilot-Schema
- das bestehende Schema bleibt unverändert; die laufende Anwendung wird nicht auf das Pilot-Schema umgeschaltet
- nach der Einrichtung enthält das Pilot-Schema keine Vereine, Spieler, Stadien, Ligen, Wettbewerbe und keinen Spielstand. Alte Datenmigrationen, die solche Zeilen anlegen (T0-Bericht 8.4), dürfen dort nichts hinterlassen. Replit belegt das mit Zeilenzahlen

**Zu N6, N7, N8 (Schutzbereiche).** A2 Punkt 4 und der Reset-Befehl in T5 lauten damit neu. Geschützt sind:

1. Schiedsrichter (Katalog, ohne alte Spiele und Sim-Zähler)
2. Sponsoren (Katalog, ohne alte Verträge, Angebote und Erträge)
3. Benutzerkonten und Profil nach N6
4. Nationen (Code und Bilddateien, keine Tabelle)
5. Regeln und Parameter nach N7

Dazu die Dortmund-Szene nach E41 über FMI-ID 907.

**Zu N10 (Startwert).**

- Der Quellwert von Transfermarkt bleibt leer. Der Server legt zusätzlich einen Marktwertpunkt 50.000 € mit dem Kennzeichen „Startwert" und dem Datum des Erhebungstags an
- Gehalt: 250 € je Pflichtspiel (50.000 € nach der Regel 5.000 € je 1 Mio. €)
- Die U21-Grenze „höchstens 3 Mio. €" gilt als erfüllt
- Gilt für jeden Spieler ohne TM-Wert, auch in der 1. Mannschaft und beim späteren Spieler-Antrag
- Der Info-Eintrag bleibt bestehen und sperrt nichts
- Ein späterer echter TM-Wert ersetzt den Startwert
- Ersetzt die Vorgabe aus T1 „Marktwert NULL → Gehalt NULL und Eintrag auf der Arbeitsliste"
- Für alle anderen Felder gilt „NULL bleibt NULL" unverändert

**Zu N11 (Verweise).** Verweise mit TM-ID bleiben wie in B11 beschrieben: Der Verein steht als `nur_verweis` mit leerem Wappen drin. Wird später sein Paket hochgeladen, erkennt der Import die TM-ID, wertet den Verweis zum vollen Verein auf, und Wappen und Verlinkung stimmen überall ohne Nacharbeit.

## In T0 bestätigt, keine Entscheidung nötig

- Kadergrenze: 60 auf NLZ-Stufe 0 (Basis 60, Aufschlag 0 / 3 / 6 / 10 je Stufe), Mindestkader 18
- CMTracker-Stand `26091500` ist FC 27 vom 15.09.2026
- Der Info-Eintrag für den leeren U21-Mittelfeldplatz steht im Paket (N2 erfüllt)
- Abnahmepunkt 5 liest sich nach E57 und E58: beide Quellen, wenn vorhanden; Nur-FM ist erlaubt; die zwei Gems ohne FMInside sind einzeln gesperrt und sperren keine Liga
- Neue Rekordschlüssel werden gespeichert, die Anzeige in der Ruhmeshalle ist keine Pilotpflicht (E18)
- Für die Abnahme gilt die interne Prüfung des Pakets. Rohdateien der Recherche werden nicht nachgefordert

## Noch offen

Nichts, was T1 aufhält. Vor dem Kopieren nach N7 bestätigt Mark die Tabellenliste.
