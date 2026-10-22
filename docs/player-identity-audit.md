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
