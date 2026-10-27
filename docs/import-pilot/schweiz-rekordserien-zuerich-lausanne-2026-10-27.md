# Zürich und Lausanne: Nachprüfung der offenen Rekordserien

Recherche vom **27.10.2026**. Dies ist ein Rechercheergebnis, keine Freigabe
eines neuen Rekordwerts. Maßgeblich bleibt die
[Importfreigabe](schweiz-2026-10-27.md): keine Intertoto-Spiele vor 1995,
keine bloße Subtraktion, keine Neuinitialisierung von Kadern.

## Abschlussstatus

| Verein / Schlüssel | Rekordwert | Halter / Rekordzeitraum | Status |
|---|---|---|---|
| FC Zürich, TM 260 / `longest_unbeaten` | weiterhin NULL | weiterhin offen | `nicht_belegt` |
| FC Lausanne-Sport, TM 527 / `longest_win_streak_coach` | weiterhin NULL | weiterhin offen | `nicht_belegt` |

**Keine Datenbank-, Paket- oder Importskriptänderung.** Die beiden Felder
bleiben fachlich offen. Die unten genannten Zahlen sind abgegrenzte
Recherchebefunde, ausdrücklich keine nachgepflegten Vereinsrekorde.
Auch Luzerns und Sions Felder werden nicht angefasst.

## Verfügbare und fehlende Ausgangsbelege

Das in der Importdokumentation genannte Originalarchiv
`attached_assets/schweiz_vereinspakete_2026-10-27_1793101337227.zip` und die
bisherige `generated-artifacts/schweiz-2026-10-27/provenance.json`
waren in dieser Arbeitskopie nicht vorhanden. Deshalb konnten ursprüngliche
Werte, Zeiträume und Trainer nicht erneut aus der Lieferung ausgelesen werden.
Die dokumentierten sechs bzw. fünf alten Intertoto-Spiele sind **kein**
ausreichender Ausgangspunkt für eine Ersatzberechnung.

Es wurde weder ein neues Originalarchiv noch eine vermeintlich ursprüngliche
`provenance.json` erzeugt. Neue Abrufe liegen getrennt unter
`generated-artifacts/schweiz-2026-10-27/record-research/`.
Diese ignorierten Arbeitsdateien sind nicht Bestandteil des Git-Commits.
Die entscheidenden Befunde und Spielbelege stehen daher auch hier.

## FC Zürich: vollständiger Archivabruf, aber kein freigegebener Allzeitwert

Quellen:

- [dbFCZ, Umfang des Archivs](https://www.dbfcz.ch/):
  5.090 erfasste Spiele vom 15.08.1920 bis 19.09.2026.
- [Chronologische Spielliste](https://www.dbfcz.ch/team.php?team_id=1&spielliste=1&s=0):
  alle **204 Seiten** abgerufen, 203 × 25 + 15 = 5.090 Zeilen,
  5.090 unterschiedliche Spiel-URLs.
- [Vereinsbilanz und Kategorien](https://www.dbfcz.ch/team.php?team_id=1).
- [Direktbeleg des kritischen Ligacupspiels](https://www.dbfcz.ch/spiel.php?spiel_id=2046).
- [Transfermarkt-Saisonübersicht 1976/77](https://www.transfermarkt.de/fc-zurich/spielplan/verein/260/saison_id/1976)
  als ergänzende Quelle, nicht als Ersatz des vollständigen Archivabrufs.

### Auswertungsumfang und Ergebnis

Die Auswertung verwendet Datum, Heim-/Auswärtsrolle, Ergebnis, Wettbewerb
und individuelle Spiel-URL. Freundschaftsspiele (1.372), alter
`IFC (Internationaler Fussballcup)` (106), Alpencup (19) und Och Cup (5)
wurden für einen ausdrücklich so abgegrenzten Pflichtspielvergleich
ausgenommen: **3.588 Spiele verbleiben**. Die sechs separat als `UI-Cup`
erfassten Spiele bleiben enthalten; nicht pauschal alle UI-Spiele löschen.
Alpen-/Och-Cup-Ausschluss ist hier eine Untersuchungsvariante, keine neue
allgemeine Importfreigabe. Eine Kontrollauswertung mit diesen beiden
Kategorien änderte das Maximum vor Elfmeterschießen nicht.

Chronologisch sortiert ergibt sich unter Wertung des Ergebnisses **vor
Elfmeterschießen** ein Maximum von **21 Spielen**, FC Zürich,
**29.05.1976–07.11.1976**. Enthalten sind 14 Ligaspiele, vier
Meistercupspiele, zwei Schweizer-Cupspiele und ein Ligacupspiel.
Forfait-Angaben werden gegenüber dem zunächst angezeigten Ergebnis
berücksichtigt.

**Entscheidender Vorbehalt:** Das Ligacupspiel am 07.08.1976 endete nach
120 Minuten 4:4, Zürich verlor aber das Elfmeterschießen. dbFCZ zeigt
`4:4 (8:7 n.P.)`; der Detailtext bestätigt das Ausscheiden. Bei entscheidender
Wertung des Elfmeterschießens ist dies eine Niederlage und trennt die Serie.
In dieser zweiten Auswertung beträgt das Maximum im untersuchten Bestand
**18**, zweimal erreicht:

- 20.09.1975–13.03.1976;
- 19.03.2006–29.07.2006.

Damit sind weder 21 noch 18 ohne weitere Einordnung als historischer
Allzeitrekord freigegeben. Die historische Paket-Zählweise ist mangels
Originalbeleg nicht geprüft; die Ergebnissemantik der SIM-Rekordberechnung
ersetzt keinen historischen Beleg. Außerdem reicht der vorliegende Abruf
nicht vor 1920 und nicht über den 19.09.2026 hinaus. Eine Bestandsauswertung
ist kein Nachweis aller Spiele seit Vereinsgründung oder bis zum
Recherchetag.

### Vollständige 21er-Kandidatenreihe mit Begrenzungsspielen

Ergebnisse immer aus Heimsicht. Die Zeilen „davor“ und „danach“ zählen nicht
zur Serie; ausgeschlossenes Intertoto unterbricht die gefilterte Reihe nicht.

| Nr. | Datum | Heim – Gast | Ergebnis | Wettbewerb | dbFCZ-Spiel |
|---|---|---|---|---|---|
| davor | 23.05.1976 | Young Boys – FCZ | 4:2 | Ligacup | [2066](https://www.dbfcz.ch/spiel.php?spiel_id=2066) |
| 1 | 29.05.1976 | FCZ – Winterthur | 5:1 | Liga | [2065](https://www.dbfcz.ch/spiel.php?spiel_id=2065) |
| 2 | 05.06.1976 | Lausanne-Sports – FCZ | 0:3 | Liga | [2064](https://www.dbfcz.ch/spiel.php?spiel_id=2064) |
| 3 | 12.06.1976 | FCZ – Biel | 5:3 | Liga | [2061](https://www.dbfcz.ch/spiel.php?spiel_id=2061) |
| 4 | 07.08.1976 | Grasshoppers – FCZ | 4:4, 8:7 n.P. | Ligacup | [2046](https://www.dbfcz.ch/spiel.php?spiel_id=2046) |
| 5 | 14.08.1976 | FCZ – Neuchâtel Xamax | 6:1 | Liga | [2044](https://www.dbfcz.ch/spiel.php?spiel_id=2044) |
| 6 | 21.08.1976 | Grasshoppers – FCZ | 2:2 | Liga | [2043](https://www.dbfcz.ch/spiel.php?spiel_id=2043) |
| 7 | 28.08.1976 | FCZ – Chênois | 2:0 | Liga | [2041](https://www.dbfcz.ch/spiel.php?spiel_id=2041) |
| 8 | 01.09.1976 | Lausanne-Sports – FCZ | 1:1 | Liga | [2040](https://www.dbfcz.ch/spiel.php?spiel_id=2040) |
| 9 | 11.09.1976 | Bellinzona – FCZ | 0:3 | Liga | [2033](https://www.dbfcz.ch/spiel.php?spiel_id=2033) |
| 10 | 15.09.1976 | Rangers FC – FCZ | 1:1 | Meistercup | [2037](https://www.dbfcz.ch/spiel.php?spiel_id=2037) |
| 11 | 18.09.1976 | FCZ – Basel | 1:0 | Liga | [2036](https://www.dbfcz.ch/spiel.php?spiel_id=2036) |
| 12 | 26.09.1976 | Lugano – FCZ | 2:4 | Schweizer Cup | [2035](https://www.dbfcz.ch/spiel.php?spiel_id=2035) |
| 13 | 29.09.1976 | FCZ – Rangers FC | 1:0 | Meistercup | [2034](https://www.dbfcz.ch/spiel.php?spiel_id=2034) |
| 14 | 02.10.1976 | Young Boys – FCZ | 1:1 | Liga | [2032](https://www.dbfcz.ch/spiel.php?spiel_id=2032) |
| 15 | 13.10.1976 | FCZ – Winterthur | 4:0 | Liga | [2031](https://www.dbfcz.ch/spiel.php?spiel_id=2031) |
| 16 | 16.10.1976 | Vevey Sports – FCZ | 0:2 | Schweizer Cup | [2024](https://www.dbfcz.ch/spiel.php?spiel_id=2024) |
| 17 | 20.10.1976 | FCZ – TPS Turku | 2:0 | Meistercup | [2025](https://www.dbfcz.ch/spiel.php?spiel_id=2025) |
| 18 | 24.10.1976 | FCZ – Servette FC | 1:1 | Liga | [2023](https://www.dbfcz.ch/spiel.php?spiel_id=2023) |
| 19 | 30.10.1976 | St. Gallen – FCZ | 1:3 | Liga | [2022](https://www.dbfcz.ch/spiel.php?spiel_id=2022) |
| 20 | 03.11.1976 | TPS Turku – FCZ | 0:1 | Meistercup | [2021](https://www.dbfcz.ch/spiel.php?spiel_id=2021) |
| 21 | 07.11.1976 | FCZ – Sion | 3:0 | Liga | [2016](https://www.dbfcz.ch/spiel.php?spiel_id=2016) |
| danach | 13.11.1976 | Neuchâtel Xamax – FCZ | 2:1 | Liga | [2015](https://www.dbfcz.ch/spiel.php?spiel_id=2015) |

Die sechs **ausgeschlossenen** IFC-Spiele dazwischen sind separat belegt:
[26.06., 1:0 in Brno](https://www.dbfcz.ch/spiel.php?spiel_id=2055),
[03.07., 4:1 gegen Austria](https://www.dbfcz.ch/spiel.php?spiel_id=2054),
[11.07., 0:0 gegen Duisburg](https://www.dbfcz.ch/spiel.php?spiel_id=2053),
[17.07., 2:4 bei Austria](https://www.dbfcz.ch/spiel.php?spiel_id=2052),
[24.07., 3:1 in Duisburg](https://www.dbfcz.ch/spiel.php?spiel_id=2051),
[31.07., 0:1 gegen Brno](https://www.dbfcz.ch/spiel.php?spiel_id=2049).
Es wurde also neu chronologisch gefiltert und gezählt, nicht sechs von
einer gelieferten Zahl abgezogen. Dies ist auch keine Behauptung, dass die
hier gefundenen sechs Spiele die ursprüngliche Paketserie bildeten.

## Lausanne: Saisonreihen vorhanden, Trainer-Allzeitrekord weiter offen

Abgerufene Quellen:

1. [Spielplan 1964/65](https://www.transfermarkt.de/fc-lausanne-sport/spielplan/verein/527/saison_id/1964):
   40 Spiele, verteilt auf Nationalliga A (26), Europapokal der Pokalsieger
   (7), Schweizer Cup (1) und International Football Cup (6).
   Schon diese Übersicht zeigt, warum eine reine Ligafolge nicht genügt.
2. [Spielplan 2003/04](https://www.transfermarkt.de/fc-lausanne-sport/spielplan/verein/527/saison_id/2003):
   26 Ligaspiele, 21 Siege, zwei Remis und drei Niederlagen.
3. [Spielplan 2004/05](https://www.transfermarkt.de/fc-lausanne-sport/spielplan/verein/527/saison_id/2004):
   zusätzlich zur Liga auch Aufstiegsplayoffs, Schweizer Cup und
   Cup-Qualifikation. Diese Wettbewerbe dürfen bei einer
   wettbewerbsübergreifenden Serie nicht fehlen.
4. [Trainerhistorie](https://www.transfermarkt.de/fc-lausanne-sport/mitarbeiterhistorie/verein/527):
   nennt Jochen Dries für 01.07.2003–30.06.2004, weist für ihn aber **0**
   verknüpfte Spiele aus. Eine Amtszeit ist kein Einzelspielnachweis.

### Konkreter Suchkandidat, ausdrücklich kein Trainerrekord

Chronologisch enthält der Ligaspielplan 2003/04 folgende neun Siege
hintereinander. Der nachgeholte 14. Spieltag gehört zwischen den 17. und
18. Spieltag; **nicht nach Spieltagsnummer zählen**.

| Datum | Heim – Gast | Ergebnis | Spieltag | TM-Spielbericht |
|---|---|---|---|---|
| davor: 20.03.2004 | Collombey – Lausanne | 4:3 | 15 | [2649015](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649015) |
| 28.03.2004 | Lausanne – Epalinges | 4:1 | 16 | [2649022](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649022) |
| 03.04.2004 | Geneva – Lausanne | 1:3 | 17 | [2649029](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649029) |
| 08.04.2004 | Lausanne – Pully | 1:0 | 14 | [2649008](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649008) |
| 18.04.2004 | Lausanne – Signal | 5:1 | 18 | [2649036](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649036) |
| 23.04.2004 | Lancy-Sports – Lausanne | 0:4 | 19 | [2649039](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649039) |
| 30.04.2004 | Lausanne – Visp | 6:2 | 20 | [2649046](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649046) |
| 08.05.2004 | La Tour – Lausanne | 2:3 | 21 | [2649055](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649055) |
| 16.05.2004 | Lausanne – Châtel-St-Denis | 4:1 | 22 | [2649064](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649064) |
| 22.05.2004 | Savièse – Lausanne | 1:3 | 23 | [2649072](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649072) |
| danach: 29.05.2004 | Lausanne – UGS Genève | 1:1 | 24 | [2649080](https://www.transfermarkt.de/spielbericht/index/spielbericht/2649080) |

Diese Folge ist nur ein **Ligabefund**, keine nachgewiesene vollständige
Pflichtspielserie und keine abgesicherte Trainerzuordnung. Es fehlen
wettbewerbsübergreifende Vollständigkeit, Einzelspiel-Trainerbelege und
der Vergleich mit allen anderen Trainerperioden. Die drei abgerufenen
Saisonübersichten sind keine vollständige Vereinsgeschichte. Die in der
Lieferdokumentation erwähnten fünf Intertoto-Spiele erlauben weder die
Zuordnung zu Dries noch zu einem anderen Trainer.

## Was für eine spätere Nachpflege noch fehlen würde

- Originalarchiv oder gesicherter Originalrekord mit Zeitraum und Quellen;
- Zürich: eindeutige historische Zählregel für Elfmeterschießen und
  belastbare zeitliche Abdeckung des beanspruchten Rekords;
- Lausanne: vollständige Pflichtspielreihen der relevanten Trainerperioden,
  einschließlich Begrenzungsspielen, Pokal/Qualifikation und Trainerbelegen;
- erst danach gezielte Nachpflege ausschließlich des belegten
  historischen Feldes samt Quellen, nicht erneuter Vereins-/Kaderimport.

Die Recherche endet daher für **beide Rekordfelder ausdrücklich ungeklärt**.
