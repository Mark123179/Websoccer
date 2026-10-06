# Import-Neuaufbau: Nachtrag 9 zur Übergabe

Stand: 06.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md` und den Nachträgen 1 bis 8

Dieser Nachtrag bestätigt das BVB-Paket v2 und regelt, was bei einem erneuten Upload mit Arbeitsliste, Handeinträgen und Einzelsperren geschieht. Er ergänzt den Umfang von T3 und hat bei Widersprüchen Vorrang vor Teil A, Teil B, Teil C und den Nachträgen 1 bis 8.

Alle Entscheidungen hat Mark am 06.10.2026 einzeln getroffen.

## Befund, der die Entscheidungen auslöst

Gelesen im Replit-Code, Stand T2 (`game/club_import/package_service.py`, `package_validation.py`, `game/import_schema.py`):

- Jeder Eintrag der Arbeitsliste hängt am einzelnen Upload (`ImportIssue.package`). Ein neues Paket legt alle Einträge neu an, die alten bleiben offen. Nach v1 und v2 stünden 284 Einträge da, davon 128 doppelt.
- Der Erledigt-Status und nachgetragene Werte hängen am alten Eintrag. Der neue Upload kennt sie nicht.
- Die Einzelsperre wird bei jedem Upload allein aus den Lücken des Pakets gesetzt.

Ohne Befund: Die Prüfung nimmt den zusätzlichen Schlüssel `potential_range` an. Der Import schreibt das neue Potenzial und rechnet die Stärke je Spieler neu. Im Quellstand-Archiv entsteht je geändertem FMInside-Block ein neuer Eintrag, die alten bleiben als Beleg.

## Entscheidungen

| # | Entscheidung |
|---|---|
| N42 | **Das BVB-Paket v2 ist bestätigt, die 28 Info-Lücken „FMInside nennt kein Potenzial (Dynamic)" bleiben entfernt.** Das ergänzt N40: Das Paket unterscheidet sich vom ersten in den drei Feldern, in den 28 Lücken, in den Zählwerten und in der Prüfsumme |
| N43 | **Einträge der Arbeitsliste werden mitgeführt.** Ein Eintrag gehört zum Verein und wird an Gegenstand und Feld erkannt. Gleiche Lücke im neuen Paket: Der Eintrag bleibt mit seinem Status. Lücke fehlt im neuen Paket: Der Eintrag wird als „durch neues Paket erledigt" geschlossen und bleibt nachlesbar. Neue Lücke: neuer offener Eintrag |
| N44 | **Handeinträge füllen Lücken, das Paket gewinnt.** Liefert das neue Paket an der Stelle keinen Wert, bleibt der Handeintrag stehen und der Eintrag bleibt erledigt. Liefert das Paket einen Wert, gilt der Paketwert. Weicht er vom Handeintrag ab, zeigt die Vorschau das vor der Bestätigung an. Gilt vor Ligastart und präzisiert E37 |
| N45 | **Die Einzelsperre hängt an den Daten.** Sie fällt weg, sobald der Spieler die fehlenden Quellwerte hat und eine Stärke berechnet ist. Eine von Hand nachgetragene ID allein hebt sie nicht auf. Der Eintrag lässt sich nicht von Hand abhaken, er schließt sich mit der Sperre |
| N46 | **Servernachweis für v2 durch Replit, der Pilot bleibt auf v1.** Replit spielt die Folge v1 → v2 als automatischen Test durch, der im Pilot nichts hinterlässt, und meldet die Zahlen als neunten Berichtspunkt. Marks Creator-Upload von v2 zeigt danach eine Vorschau mit echten Änderungen (N41) |

## Zu N42: Das Paket v2

- Datei: `bvb_vereinspaket_2026-10-05_v2.zip`
- `data_sha256`: `ab3925f40f1b84ddd103a25928d61aa7feb3c36d9036890ff802131896751391`
- Formatversion 1, Erhebungstag 05.10.2026, Quelle FM26 26.2.0. Die Spannen wurden am 06.10.2026 gelesen.
- 51 Spieler, 49 mit FMInside-Block. 28 mit `potential_range` gefüllt, 21 mit `potential_range: null`.
- Lücken: 115 (2 Einzelsperren, 113 Info, 0 sperrend).
- Die Stufe (`code`) ist ein- oder zweistellig: -5, -55, -6, -65, -7, -75, -8, -85, -9, -95.

Alle 28 Spannen waren lesbar. Ein unabhängiger Vergleich mit dem ersten Paket hat bestätigt, dass sonst nichts geändert ist.

### Wirkung auf die maximale Stärke

Die Regel aus N39 gilt für jeden Dynamic-Spieler, auch mit CMTracker-Eintrag. Marks eigenes Beispiel deckt das: Samuele Inácio hat einen CMTracker-Eintrag.

Die Rechnung selbst bleibt unverändert (`calculate_potential_200`): Bei zwei Quellen ist das Potenzial die Summe beider Werte, bei einer Quelle der doppelte Wert. Bisher zählte bei den 14 Dynamic-Spielern mit CMTracker nur CMTracker. Jetzt zählen beide Quellen.

| Spieler | FMInside neu | CMTracker | Potenzial 0–200 bisher | Potenzial 0–200 neu |
|---|---|---|---|---|
| Ethan Nwaneri | 95 | 86 | 172 | 181 |
| Joane Gadou | 90 | 85 | 170 | 175 |
| Jobe Bellingham | 85 | 83 | 166 | 168 |
| Konstantinos Karetsas | 85 | 88 | 176 | 173 |
| Justin Lerma | 85 | 87 | 174 | 172 |
| Mathis Albert | 85 | 88 | 176 | 173 |
| Samuele Inácio | 80 | 86 | 172 | 166 |
| Kauã Prates | 80 | 85 | 170 | 165 |
| Mussa Kaba | 80 | 85 | 170 | 165 |
| Enzo dos Santos | 75 | 85 | 170 | 160 |
| Almugera Kabar | 75 | 79 | 158 | 154 |
| Filippo Mane | 75 | 79 | 158 | 154 |
| Luca Reggiani | 70 | 82 | 164 | 152 |
| Elias Benkara | 70 | 79 | 158 | 149 |

Bei 3 Spielern steigt die Obergrenze, bei 11 sinkt sie. Die aktuelle Stärke bleibt bei allen gleich.

Die 14 Dynamic-Spieler ohne CMTracker hatten bisher keine Stärke. Sie bekommen jetzt das Doppelte des oberen Werts als Potenzial, zum Beispiel Luke Fahrenhorst 160 und Bennedikt Wüstenhagen 100.

## Zu N43: Mitführen im Einzelnen

- Schlüssel eines Eintrags: Verein, Gegenstand (Art und Bezug, zum Beispiel `player` und `tm:1058359`) und Feld. Text und Schwere dürfen sich mit dem neuen Paket aktualisieren.
- Der Eintrag merkt sich, mit welchem Paket er zuletzt bestätigt wurde.
- „Durch neues Paket erledigt" ist ein eigener Abschluss, getrennt von „von Hand erledigt". So bleibt sichtbar, wer geschlossen hat.
- Lesart von Claude: Kommt eine Lücke in einem späteren Paket zurück, wird ein vom Paket geschlossener Eintrag wieder geöffnet. Ein von Hand erledigter bleibt erledigt, solange N44 den Handeintrag stehen lässt.
- Gilt für alle Arten von Einträgen: Lücken aus dem Paket, Vereinsnamen ohne TM-ID (N11), Prüfpool (N36), fehlende Bilder.
- Die Vorschau zeigt vor der Bestätigung, wie viele Einträge neu entstehen, bleiben und geschlossen werden.

Für v2 nach v1 heißt das: 156 Einträge bleiben 156 Zeilen. Davon sind 128 offen und 28 durch das neue Paket erledigt.

## Zu N44: Handeinträge im Einzelnen

Betroffen sind externe IDs mit Status `von_hand`, nachgetragene TM-IDs zu Vereinsnamen (N11), bestätigte Verknüpfungsvorschläge (N12) und von Hand zugeordnete Prüfpool-Spieler (N36).

- Paket ohne Wert an der Stelle: Der Handeintrag bleibt, der Status bleibt `von_hand`.
- Paket mit demselben Wert: Der Wert bleibt, der Status wird `gefunden`. Die Vorschau meldet nichts.
- Paket mit anderem Wert: Der Paketwert gilt. Die Vorschau listet alten und neuen Wert vor der Bestätigung.
- Würde ein Paketwert einem Spieler oder Verein eine andere Identität geben, gilt weiter die Regel aus T2: kein automatisches Zusammenführen, Eintrag auf der Arbeitsliste.
- Nach Ligastart gilt unverändert die Schreibmaske aus N30.

## Zu N45: Einzelsperre im Einzelnen

- Die Sperre wird aus dem Datenstand nach dem Import abgeleitet und nicht mehr allein aus den Lücken des Pakets.
- Sie besteht, solange die im Paket verlangten Quellwerte fehlen oder keine Stärke berechnet ist.
- Eine von Hand nachgetragene FMI-ID wird gespeichert und hilft dem nächsten Paketbau. Sie bringt kein Rating mit und hebt die Sperre deshalb nicht auf.
- Die Einzelsperre fällt über ein neues Paket weg, das die Werte liefert.
- BVB: Takato Yamamoto und Bjarki Gardarsson bleiben gesperrt.

## Zu N46: Der Test v1 → v2

Ablauf: leerer Bestand, v1 einlesen, v2 einlesen, v2 noch einmal einlesen. Der Test läuft in einer eigenen Testdatenbank oder in einer Transaktion, die zurückgerollt wird. Der Pilot steht danach unverändert auf v1.

Erwartete Werte nach v2:

| Größe | nach v1 | nach v2 |
|---|---|---|
| Spieler | 51 | 51 |
| Spieler mit berechneter Stärke | 35 | 49 |
| Einzelsperren | 2 | 2 |
| Einträge im Quellstand-Archiv | 83 | 132 |
| Marktwertpunkte | 637 | 637 |
| Transfers | 322 | 322 |
| Rekorde, Titel-Einzeleinträge | 24, 30 | 24, 30 |
| Arbeitsliste: Zeilen | 156 | 156 |
| Arbeitsliste: offen | 156 | 128 |
| Arbeitsliste: durch Paket erledigt | 0 | 28 |
| Zeilen in `game_club` | 1 | 1 |

Stichprobe Potenzial und Basis auf der Skala 0–200:

| Spieler | Basis | Potenzial |
|---|---|---|
| Ethan Nwaneri | 145 | 181 |
| Samuele Inácio | 120 | 166 |
| Luca Reggiani | 116 | 152 |
| Luke Fahrenhorst | 90 | 160 |
| Bennedikt Wüstenhagen | 92 | 100 |

Der dritte Schritt (v2 erneut) ändert keine Zeile.

Weicht ein Wert ab, meldet Replit den Wert und die Ursache und ändert nichts an der Stärkeformel.

## Ergänzung zum Umfang von T3

- Arbeitsliste mit Mitführen nach N43
- Vorschau zeigt geänderte Handeinträge (N44) und die Bilanz der Arbeitsliste (N43)
- Einzelsperre aus dem Datenstand (N45), Einträge dieser Art nicht von Hand abhakbar
- Test v1 → v2 (N46)

Ist T3 schon gebaut, kommen diese Punkte als Korrektur vor dem Halt dazu. Es bleibt bei einem Halt am Ende von T3 und T4.

## Ergänzung zum Bericht am Ende von T3 und T4

9. Test v1 → v2: die Tabelle aus „Zu N46" mit den gemessenen Werten, die fünf Stichproben, Nachweis, dass der Pilot weiter auf v1 steht.
10. Arbeitsliste: Schlüssel eines Eintrags, Verhalten bei Wiederkehr einer Lücke, Bildschirmfoto der Vorschau mit Bilanz.

## Ergänzung zur Abnahme durch Mark

Zu Punkt 1 und 7 aus Nachtrag 8: Der Upload von v2 auf den Pilot mit v1 zeigt in der Vorschau 28 geänderte Potenziale, 14 neue Stärken und 28 Einträge, die geschlossen werden. Nach der Bestätigung stehen 128 offene Einträge auf der Arbeitsliste.

## Für das Werkzeug der zweiten Stufe

- Die Spanne steht im statischen HTML der Spielerseite: Attribut `data-site-tooltip` am Element `span.card.dynamic` in `div.player-hero-ratings`. Ein Browser ist dafür nicht nötig.
- Ist eine Spanne gelesen, entsteht keine Lücke zum Potenzial. Ist sie nicht lesbar, bleibt `potential` leer und die Info-Lücke entsteht wie bisher.

## Freigabe

Freigegeben: die Ergänzungen zu T3 nach diesem Nachtrag. Unverändert nicht freigegeben: Reset-Befehl (T5), Sicherung der Dortmund-Szene, jede Änderung an der Stärkeformel.
