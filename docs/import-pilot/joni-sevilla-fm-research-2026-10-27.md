# Joni Hernández und Sevillas Adrián Pérez: erweiterte FM-Recherche

Stand: 27.10.2026. **Keine Ersatz-FM-ID bestätigt; beide Fälle bleiben offen.**
Dies ist ein Rechercheergebnis, keine abgeschlossene Identitätsfreigabe.
Die acht ursprünglichen Fälle und die drei bereits belegten Korrekturen stehen
im [bisherigen Bericht](laliga-fm-identities-2026-10-27.md).

## Verbindliche Zielidentitäten

Die direkten Transfermarkt-Profile wurden erneut gelesen:

| Spieler | TM-ID | Vollname | Geburtstag | Position |
| --- | --- | --- | --- | --- |
| Joni Hernández | [1533553](https://www.transfermarkt.com/player/profil/spieler/1533553) | Jonathan Hernández Jones | 22.05.2008 | Rechtsaußen |
| Adrián Pérez, Sevilla | [1596653](https://www.transfermarkt.com/player/profil/spieler/1596653) | Adrián Francisco Pérez Monreal | 05.09.2007 | Rechtsverteidiger |

Joni wird aktuell bei Barcelona Atlètic geführt, zuvor Tenerife.
Transfermarkt nennt außerdem UD San Fernando, Valencia und Colegio Salgui als
Jugendvereine. Das ist Suchkontext, kein FM-Identitätsbeleg.
Sevillas Adrián wird bei Sevilla Atlético geführt.

## Neuer Hinweis: „Jony Hernandez“ ohne FM-ID

Die öffentliche, von Sortitoutsi verlinkte [FMRef-ID-Suche](https://fmref.com/)
liefert bei **`Jony Hernandez`** genau einen Treffer:

```json
{
  "classification_id": "player",
  "fm_id": "",
  "gender": "",
  "id": "1947315",
  "name": "Jony Hernandez",
  "nation": {"fm_id": 796, "id": 172, "name": "Spain"},
  "search_terms": [],
  "team": {"fm_id": 1668, "id": 5614, "name": "F.C. Barcelona Atlètic"},
  "type_id": "person"
}
```

Der Name und Verein machen diesen Datensatz zu einem relevanten Hinweis.
**Er enthält aber weder eine FM-UID noch ein Geburtsdatum.** `1947315` ist
das separate interne Indexfeld `id`, ausdrücklich **nicht** `fm_id`.
Auch die Vereins-ID `1668` ist keine Spieler-ID. Keinen dieser Werte als
Ersatz-FM-ID speichern. Ob dieser Eintrag tatsächlich die Zielperson beschreibt,
ist damit noch nicht eindeutig belegt.

FMRef ist ein versionsübergreifender Index: Ein Treffer dort beweist nicht
automatisch die Existenz in der FM26-Standarddatenbank. Das wurde zusätzlich
an Adriáns Namensvetter mit UID 2002044764 sichtbar, siehe unten.

### Suchumfang und Reproduktion

Abgefragt wurde die von der öffentlichen FMRef-Oberfläche genutzte
Typesense-Suche, Collection `detailed_game_items`, Felder
`name,fm_id,search_terms`. Die folgenden abschließenden Abfragen verwendeten
`num_typos=0`, `drop_tokens_threshold=0`, `prefix=false` und 100 Treffer pro
Seite; alle Treffer wurden abgerufen. Vorherige unscharfe Abfragen dienten
nur der Kandidatensuche.

| Suchtext | Treffer / abgerufen |
| --- | --- |
| Joni | 192 / 192 |
| Jony | 57 / 57 |
| Jonathan Hernandez | 22 / 22 |
| Jonathan Hernández Jones | 0 / 0 |
| Hernandez Jones | 0 / 0 |
| Perez Monreal | 0 / 0 |
| Adrián Francisco | 9 / 9 |
| Adrian Perez | 37 / 37 |
| Jony Hernandez | 1 / 1 |

Die Namen und hinterlegten Vollnamens-Aliasse wurden geprüft, nicht nur die
ersten Suchtreffer oder die Hauptvereine. Kein Ergebnis liefert eine belegte
Ersatz-UID zusammen mit dem exakten Zielgeburtstag. Ein leeres oder unvollständiges
Suchergebnis bleibt eine Grenze dieses Indexes, kein Nachweis der FM-Abwesenheit.

## Direkt geprüfte zusätzliche Kandidaten

Die folgenden UIDs stammen aus tatsächlichen Suchtreffern, nicht aus
benachbarten Nummern. Die verlinkten Sortitoutsi-Seiten wurden direkt gelesen.
Sie stellen FM-Daten dar, keine unabhängigen Belege realer Geburtstage.

| Kandidat | Direktbeleg | Ergebnis |
| --- | --- | --- |
| Joni, UD San Fernando | [2000403115](https://sortitoutsi.net/football-manager-2026/person/2000403115/joni) | FM-DOB **01.01.2003**. Trotz passendem früherem Jugendvereinsnamen kein Beleg für Joni vom 22.05.2008. Nicht übernehmen. |
| Joni, CD Marino | [2000186868](https://sortitoutsi.net/football-manager-2026/person/2000186868/joni) | FM-DOB **21.07.2001**; Indexalias Jonathan García Farrais. Andere Identität. |
| Joni | [67255780](https://sortitoutsi.net/football-manager-2026/person/67255780/joni) | Indexalias Jonathan Serrano Bargada. Kein UID-/DOB-Beleg für Hernández Jones. |
| Jony | [2000278382](https://sortitoutsi.net/football-manager-2026/person/2000278382/jony) | FM-DOB **12.07.2001**. Nicht übernehmen. |
| Jony, Real Avilés B | [2000393057](https://sortitoutsi.net/football-manager-2026/person/2000393057/jony) | FM-DOB **26.10.2005**. Nicht übernehmen. |
| Adrián Pérez | [2002044764, Versionsübersicht](https://sortitoutsi.net/football-manager/person/2002044764/adrian-perez) | Die Übersicht verlinkt **FM24 Update / 2025**, R. Madrid, AM RL. Die FM26-URL liefert kein Personendatenprofil mit DOB. Kein Beleg für Sevillas Rechtsverteidiger. |
| Adrián Pérez, St Joseph's | [2000520334](https://sortitoutsi.net/football-manager-2026/person/2000520334/adrian-perez) | FM-DOB **07.04.1999**. Nicht übernehmen. |
| Adrián Pérez, Becerril | [2000482810](https://sortitoutsi.net/football-manager-2026/person/2000482810/adrian-perez) | FM-DOB **03.10.2005**. Nicht übernehmen. |

Die bereits widerlegten IDs bleiben widerlegt: **2000351880 gehört Toni
Fernández**, **2000280111 gehört dem Athletic-Offensivspieler**.
Die Geburtstagskonflikte anderer Spieler werden durch diese Recherche nicht
aufgehoben.

## Zusätzliche Kader- und Webquellen

Direkt gelesen wurden:

- Sortitoutsi FM26:
  [Barcelona](https://sortitoutsi.net/football-manager-2026/team/1708/barcelona),
  [Tenerife](https://sortitoutsi.net/football-manager-2026/team/1680/tenerife),
  [Sevilla](https://sortitoutsi.net/football-manager-2026/team/1759/sevilla),
  [Sevilla Atlético](https://sortitoutsi.net/football-manager-2026/team/4202262/sevilla-atletico).
  Die Hauptvereinsseiten sind **keine vollständigen Nachwuchsnachweise**.
- FMInside FM26:
  [Tenerife mit B-/U19-Spielern](https://fminside.net/clubs/7-fm-26/1680-tenerife),
  [Sevilla mit B-/U19-Spielern](https://fminside.net/clubs/7-fm-26/1759-sevilla)
  und der verfügbare erste Auszug von
  [Barcelona](https://fminside.net/clubs/7-fm-26/1708-fc-barcelona).
  Der neue Barcelona-Auszug war abgeschnitten; daraus wird keine vollständige
  Nachwuchsprüfung behauptet. Die vorherige Prüfung ist im Ausgangsbericht dokumentiert.
- FM Scout FM26:
  [Tenerife](https://www.fmscout.com/club/tenerife.html?rev=26),
  [Sevilla](https://www.fmscout.com/club/sevilla.html?rev=26),
  [Barcelona](https://www.fmscout.com/club/barcelona.html?rev=26).
  Keine dieser gelesenen Seiten lieferte den benötigten UID-/DOB-Beleg.
- Ergänzende Websuchen mit Joni/Jony/Jonathan Hernández Jones,
  Adrián/Adrian Pérez Monreal, Vereinen und Geburtsdaten, auch auf
  FMInside und Sortitoutsi begrenzt. Such-Snippets wurden nicht als
  ausreichender Freigabebeleg gewertet.

## Unveränderter Workspace und nächste Beleganforderung

Es wurde **kein Import und keine schreibende Nachpflege ausgeführt**.
`scripts/resolve_laliga_fm_identities.py` bleibt ausschließlich für die drei
bereits bestätigten Zuordnungen zuständig; `issue_lifecycle.py` bleibt unverändert.
Es wurden keine Spieler zusammengeführt, Geburtstage geändert, Quellwerte
ergänzt oder Sperren aufgehoben.

Eine ausdrücklich **READ ONLY** gesetzte Datenbanktransaktion bestätigte:

- Beide Zielspieler haben weiterhin `fm_inside_id=NULL`, `import_lock=True`
  und keine aktuelle FM-Bewertung oder nichtleere FM-External-ID.
- Ihre Geburtstage bleiben 22.05.2008 bzw. 05.09.2007.
- Beide sind in der nicht spielbaren LaLiga zugeordnet.
- Das Originalarchiv hat weiterhin SHA-256
  `ac87857f81e8929450b21a71973b664e1abbd61b8b435de98c491883d52c27eb`.

**Für eine Freigabe fehlt weiterhin je Spieler ein konkreter FM-Datenbank-
oder Editorbeleg mit derselben Spieler-UID, passendem Namen und exakt
übereinstimmendem Geburtsdatum sowie erkennbarer Datenbankversion.**
Ein solcher Export oder Screenshot kann gezielt geprüft werden; eine
ungeprüfte ID, ein Treffer ohne Geburtstag oder eine Geburtstagsausnahme genügt nicht.
Der neue leere „Jony Hernandez“-Indexeintrag allein schließt diese Lücke nicht.

Lokale Recherchebelege, ignoriert und nicht für Deployment/Git bestimmt:

- `generated-artifacts/laliga-2026-10-27/joni-sevilla-web-evidence.json`
- `generated-artifacts/laliga-2026-10-27/joni-sevilla-fmref-evidence.json`

Die maßgeblichen neuen Befunde und direkten URLs stehen absichtlich auch in
diesem versionierten Bericht: Ignorierte Rohbelege sind in späteren Forks
nicht garantiert vorhanden.
