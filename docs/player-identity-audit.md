# Bestehende Spieleridentitäten prüfen

```sh
python manage.py audit_player_identities
python manage.py audit_player_identities --format json > generated-artifacts/player-identities.json
```

Für die zweite Variante das lokale Ausgabeverzeichnis vorher anlegen.
Der Befehl prüft den gesamten Bestand der konfigurierten Datenbank ausschließlich
mit Leseabfragen. Er benötigt keine Vereinspakete und startet weder den
Paketimport noch dessen schreibenden, zurückgerollten Trockenlauf.
Insbesondere wird das nicht freigegebene St.-Pauli-Paket nicht importiert.
Es gibt keinen Reparatur-/Apply-Schalter.

## Belege und Grenzen

Verglichen werden aktive TM-, FM- und API-Football-Spiegel-IDs, kanonische
`PlayerExternalId`-Zeilen aller Quellen (einschließlich CMTRACKER), historische
FM-Spiegel-IDs und explizite `linked_player`-Verbindungen. CMTRACKER hat am
aktiven Spieler kein Spiegel-Feld. Trainernummern werden nicht mit
Spielernummern gleichgesetzt. Namen sind ausschließlich Anzeigenamen; weder
Namen noch Geburtsdaten erzeugen Identitätszuordnungen.

Jeder Befund enthält betroffene Datenbank-IDs, Namen, Vereinszuordnung,
Quell-ID-Werte samt Herkunft, kanonische Zeilen mit Eigentümer, Quell-URLs und
Match-Belegen sowie bestehende Vereinsrekord-Verweise. Verbindungen im Bericht
sind **Prüfhinweise**, keine Freigabe zur Zusammenführung.

- `split_identity`: gemeinsame IDs/Links führen zu mehreren aktiven Spielern.
- `multiple_people`: mehrere Rekordpersonen führen zu einer aktiven Identität.
- `unlinked_person`: eine gemeinsame Quell-ID belegt einen aktiven Kandidaten,
  aber die historische Person hat keinen `linked_player`.
- `conflicting_ids` / `conflicting_birth_dates`: bekannte Werte innerhalb einer
  belegten Verbindung widersprechen sich. Fehlende Werte sind kein Widerspruch.
- `missing_canonical` / `missing_mirror`: ein Gegenbeleg fehlt. Das kann auch
  regulären Altbestand betreffen und ist nicht automatisch ein Identitätskonflikt.
- `wrong_kind` / `orphan_owner`: widersprüchliche Typisierung oder fehlender
  Eigentümer einer kanonischen Zeile.

Eine historische kanonische ID mit passender Verknüpfung ist gültig; sie muss
nicht zusätzlich dem aktiven Spieler gehören. Auch eine ursprünglich beim
aktiven Spieler gespeicherte kanonische ID deckt die passende Spiegel-ID der
verknüpften historischen Person ab; daraus folgt keine ID-Übertragung.
Rein historische Personen ohne
aktives Gegenstück werden gezählt, aber nicht allein deshalb als Fehler
gemeldet. Spieler ganz ohne IDs werden nicht anhand ihrer Namen geraten.
Unbekannte IDs (`NULL`/leer) stellen keine Identität her.

Der Bericht ist deterministisch für unveränderten Bestand. Er beansprucht
keinen transaktionsübergreifenden Snapshot bei parallel laufenden Importen;
für vergleichbare Bestandsabnahmen keine parallelen Schreiber ausführen.
Exit-Code 0 bedeutet erfolgreiche Prüfung, nicht Konfliktfreiheit; dafür
`summary.affected_components` und `problems_by_code` auswerten.
Die JSON-Datei enthält Bestandsdaten und gehört nicht in Git.

## Zwei gespeicherte Prüfstände vergleichen

```sh
# Eigenständig: nur Python-Standardbibliothek, keine Django-Einstellungen,
# Datenbankverbindung, aktuellen Bestandsdaten oder Importpakete nötig.
python -m game.club_import.identity_audit_diff \
  generated-artifacts/player-identities-vorher.json \
  generated-artifacts/player-identities-nachher.json

python -m game.club_import.identity_audit_diff \
  generated-artifacts/player-identities-vorher.json \
  generated-artifacts/player-identities-nachher.json \
  --format json > generated-artifacts/player-identities-vergleich.json

# Alternativ im bereits eingerichteten Django-Projekt (ebenfalls ohne Abfragen):
python manage.py compare_player_identity_audits vorher.json nachher.json --format json
```

Die Reihenfolge ist **älterer Bericht, neuerer Bericht**. Beide Eingabedateien
bleiben unverändert; der Vergleich schreibt nur auf die Standardausgabe.
Auch der Django-Befehl führt keine System-, Migrations- oder Bestandsprüfung aus.
Es gibt weder einen Apply-Schalter noch eine automatische Reparatur.

### Schema und Zuordnung

Der Audit exportiert derzeit `schema_version: 1`, `read_only: true`, `summary`
und `findings`. Jede betroffene Komponente enthält `players`, `people`,
`problems`, `evidence`, `canonical_rows` und `record_references`.
Der Vergleich akzeptiert ausschließlich zwei Schema-1-Audits mit vollständigen
Zuordnungsbelegen; fehlende, anders typisierte oder abweichende Versionen werden
mit verständlicher Fehlermeldung abgewiesen. Vergleiche selbst sind keine
Audit-Eingabedateien.

`findings.added`, `.unchanged` und `.removed` zählen **einzelne Probleme**,
nicht Listenplätze oder ganze Komponenten. Ein Schlüssel besteht aus dem
Problemcode, seinen sachlichen Details und dem engsten verfügbaren Beleg:
typisiertem Eigentümer (`player`/`person` plus Datenbank-ID), Quelle und
Quell-ID, beteiligten Konfliktwerten beziehungsweise Geburtsdatumsbelegen.
Kanonische Zeilenprobleme werden über Eigentümer, Quelle, ID und Personentyp
zugeordnet; eine neu angelegte Zeilen-ID allein erzeugt kein neues Problem.
Namen, Vereine, URLs, Meldungstexte und Listenreihenfolgen sind keine
Identitätsschlüssel. Fehlende Geburtsdaten bleiben fehlende Werte und werden
nicht zum Nachweis einer korrigierten Identität.

Jedes Problem verweist über `before_components`/`after_components` auf die
Belege unter `components.before`/`.after`; dort bleiben die ursprünglichen
Befunddaten einschließlich kanonischer Zeilen und Rekordverweise enthalten.
Komponentenschlüssel sind deterministische Fingerabdrücke der typisierten
Eigentümer, Eigentümer-Quell-ID-Belege und expliziten Links, keine
laufenden Nummern. Eine unveränderte Lücke eines Eigentümers bleibt somit auch
beim Verbinden/Trennen einer Komponente als unverändert erkennbar.

`assignment_changes` beschreibt Überschneidungen der Komponenten anhand
typisierter Eigentümer oder gleicher `(provider, value)`-Belege:

- `merged` / **Verbunden**: mehrere vorherige Komponenten führen zu einer.
- `split` / **Getrennt**: eine vorherige Komponente führt zu mehreren.
- `reconfigured` / **Neu zugeordnet**: mehrere Komponenten auf beiden Seiten.
- `changed` / **Zuordnung geändert**: eine zu einer, aber mit geänderten
  Eigentümern, Quellbelegen oder Links.

Die Zuordnung nennt die beteiligten Komponentenschlüssel und gemeinsame
Eigentümer-/Quell-ID-Belege ausdrücklich. Sie ist ein Vergleichshinweis,
keine Behauptung, dass die Eigentümer tatsächlich dieselbe Person sind.

### Grenzen und Exit-Code

Nur problembehaftete Komponenten stehen im Audit. Ein vollständig entfallener
Befund kann daher eine erfolgreiche Nachpflege, Löschung, veränderte
Prüfbedingungen oder das Herausfallen aus einer betroffenen Komponente bedeuten.
**Nicht mehr vorhanden** ist kein automatischer Reparatur- oder
Löschungsnachweis. Eine inzwischen fehlerfreie, nicht mehr exportierte
Komponente kann nicht als Teil einer Trennung rekonstruiert werden.
Verbindungen/Trennungen beziehen sich ausschließlich auf sichtbare
Befundkomponenten. Ändern sich die tragenden Konfliktwerte, wird der alte
Widerspruch als entfallen und der neue als hinzugekommen ausgewiesen.

Für sinnvolle Vergleiche müssen die Berichte aus demselben Bestand mit
derselben Eigentümer-ID-Zuordnung und denselben Prüfregeln stammen.
Ein Neuimport mit neu vergebenen Datenbank-IDs ist kein identischer Prüfstand;
übereinstimmende Quell-IDs können dann nur eine Zuordnungsänderung belegen.
Der Vergleich kann Herkunft und zwischenzeitliche Schreibvorgänge nicht prüfen.
Die vollständigen Belege enthalten weiterhin Bestandsdaten: auch Vergleichsdateien
nur lokal aufbewahren, nicht in Git.

Exit-Code **0** bedeutet erfolgreicher Vergleich, unabhängig von Änderungen.
Ungültige Dateien/Schema-Versionen liefern einen Fehlercode ungleich 0, ohne
Teilbericht auf der Standardausgabe.
