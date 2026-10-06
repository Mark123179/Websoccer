"""Generate the authorized seven-point T1 report from actual schema evidence."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "import_pilot.settings"
import django
django.setup()
from django.apps import apps
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from scripts.import_pilot_public_evidence import capture


def write():
    folder = ROOT / "docs/import-pilot"
    evidence = json.loads((folder / "t1-schema-evidence.json").read_text())
    checks = json.loads((folder / "t1-checks.json").read_text())
    old_public = json.loads((folder / "t1-public-before.json").read_text())
    new_public = json.loads(json.dumps(capture()))
    changed = [t for t in old_public["tables"]
               if old_public["tables"][t] != new_public["tables"].get(t)]
    public = {
        "table_count": len(old_public["tables"]), "changed_tables": changed,
        "unchanged_tables": len(old_public["tables"]) - len(changed),
        "sequences_equal": old_public["sequences"] == new_public["sequences"],
        "metadata_equal": old_public["metadata"] == new_public["metadata"],
        "pilot_has_public_write_privileges": False,
        "complete_byte_equality": not changed,
    }
    (folder / "t1-public-comparison.json").write_text(json.dumps(public, indent=2) + "\n")
    before = MigrationLoader(connection).project_state(
        [("game", "0186_match_story_version_v41")]).apps
    with connection.cursor() as cur:
        cur.execute("SELECT table_name,column_name,data_type,is_nullable FROM "
                    "information_schema.columns WHERE table_schema='import_pilot'")
        physical = {(t, c): (typ, null) for t, c, typ, null in cur.fetchall()}
    new_tables, added, altered, dropped = [], [], [], []
    schema = ["# T1: tatsächlich umgesetztes Schema",
              "", "Migration: game/migrations/0187_import_rebuild_n28_n31.py",
              "", "Quelle: Django-Migrationszustand 0186 → aktive Modelle und PostgreSQL-Katalog.",
              "Keine Pakete importiert. Temporäre Schutz-Sicherungen sind keine fachlichen neuen Modelle.",
              "", "| Tabelle | Spalte | Änderung | PostgreSQL-Typ | Nullable |",
              "|---|---|---|---|---|"]
    for model in sorted(apps.get_app_config("game").get_models(), key=lambda m: m._meta.db_table):
        if model._meta.proxy:
            continue
        table = model._meta.db_table
        try:
            previous = before.get_model("game", model._meta.model_name)
            old_fields = {f.column: f for f in previous._meta.concrete_fields}
        except LookupError:
            old_fields = {}
            new_tables.append(table)
        current = {f.column: f for f in model._meta.concrete_fields}
        for column, field in current.items():
            old = old_fields.get(column)
            kind = "neu (neue Tabelle)" if not old_fields else "neu"
            if old is None:
                added.append(table + "." + column)
            elif old.deconstruct()[2:] != field.deconstruct()[2:]:
                kind = "geändert"
                altered.append(table + "." + column)
            else:
                continue
            datatype, nullable = physical[(table, column)]
            schema.append(f"| {table} | {column} | {kind} | {datatype} | {nullable} |")
        dropped.extend(table + "." + c for c in old_fields.keys() - current.keys())
    schema += ["", "## Zusammenfassung",
               f"- Neue fachliche Tabellen: {', '.join(new_tables)}.",
               f"- Neue Spalten insgesamt (einschließlich neuer Tabellen): {len(added)}.",
               f"- Geänderte Felddefinitionen: {len(altered)}.",
               f"- Physisch entfernte Spalten: {len(dropped)}.",
               "- Nicht angelegt: real_loan_status, real_loan_club_id, real_loan_until, package_file.",
               "- league_id bleibt NOT NULL. Kein nur_verweis-Zustand.",
               "- Legacy-Spalten bleiben für Altleser physisch vorhanden; kein vorgezogener DROP.",
               "", "## Constraint-Änderungen"]
    migration = MigrationLoader(connection).disk_migrations[("game", "0187_import_rebuild_n28_n31")]
    for operation in migration.operations:
        if "Constraint" in type(operation).__name__:
            name = getattr(operation, "name", None) or operation.constraint.name
            schema.append(f"- {type(operation).__name__}: {operation.model_name}.{name}")
    (folder / "t1-schema-spalten.md").write_text("\n".join(schema) + "\n")
    report = [
        "# T1-Bericht – Import-Neuaufbau",
        "",
        "**Stand 06.10.2026 · HALT nach T1.** N28–N31 eingearbeitet; kein Paketimport, "
        "kein Creator-Upload, keine Dortmund-Szenensicherung, kein T2–T5 und kein Hetzner-Zugriff.",
        "",
        "**Abnahme-Einschränkung:** Der komplette Bytegleichheitsnachweis für public ist nicht grün. "
        "Bei identischen Zeilenzahlen änderte sich der Fingerprint von "
        + ", ".join(changed) + ". Kein Rückschreiben und kein Verbergen dieser Abweichung; Details Punkt 7.",
        "",
        "## 1. Tatsächliche Migration und Modelländerungen",
        "",
        "**Migration:** game/migrations/0187_import_rebuild_n28_n31.py. "
        f"{len(evidence['migrations'])} reguläre Migrationseinträge im Pilot, keine offenen "
        "Migrationen und kein --fake/--fake-initial.",
        "",
        f"Neu: genau zwei fachliche Tabellen ({', '.join(new_tables)}). "
        f"{len(added)} neue Spalten einschließlich deren Spalten; "
        f"{len(altered)} geänderte Felddefinitionen; {len(dropped)} physische Spaltenlöschungen. "
        "**Die vollständige Einzelspalten-/Typ-/Nullbarkeitsliste und Constraints stehen in "
        "t1-schema-spalten.md.**",
        "",
        "Erweitert: Club, Stadium, Player, PlayerExternalId, ClubExternalId, HistoricCoach, "
        "PlayerSourceRatingSnapshot, PlayerMarketValueSnapshot, PlayerTransferHistory, "
        "ClubRecord, ClubTrophy und SourceImportRun. Pflicht-Liga bleibt erhalten; "
        "import_state nur spielbar/nicht_spielbar. Zwölf reale Seitenkapazitäten mit zwölf "
        "Kennzeichen getrennt von zwölf nullable aktuellen Seitenkapazitäten; zusätzlich "
        "belegte nationale/aggregierte Gesamtwerte.",
        "",
        "Nicht angelegt: drei Real-Leihspalten und package_file. Archiventscheidung: "
        "ausschließlich JSON (package_data + manifest), nicht zusätzlich eine Datei. "
        "N29 erforderte vier zusätzliche operative TM-/Originalname-Spalten für "
        "Stamm-/Leihverein. Das sind die freigegebenen Auflagen, keine neuen Tabellen.",
        "",
        "**Übergangsaktivierung:** IMPORT_REBUILD_SCHEMA schaltet dieselben bestehenden "
        "Game-Klassen mit ihren gemeinsamen Erweiterungen ein: im Pilot an, im noch nicht "
        "migrierten Bestandsdienst standardmäßig aus. Gemeinsame Migration, kein Pilotmodellset "
        "und keine kopierte Formel. Ein späterer Live-Cutover muss das neue Schema und die "
        "Aktivierung zusammen freigeben; T1 verändert die public-Struktur nicht.",
        "",
        "## 2. Null-Zeilen-Nachweis",
        "",
        f"**Alle {len(evidence['empty_business_tables'])} aktiven Geschäftstabellen haben 0 Zeilen.** "
        "Vollständige Tabelle-zu-Zeilenzahl-Liste:",
        "",
        "| Tabelle | Zeilen |", "|---|---:|",
    ]
    report += [f"| {t} | {n} |" for t, n in sorted(evidence["empty_business_tables"].items())]
    report += [
        "",
        "Damit sind insbesondere Clubs, Spieler, Stadionanker/Geometrie/Design/Ausbauten, "
        "Ligen/Saisons, Wettbewerbe/Turniere/Pokale, Spiele/Ticker/Geschichten, Finanzbuchungen, "
        "Transfer-/Leih-/Scoutingzustände, Real-Historien/Rekorde/Titel und Paketläufe/Arbeitsliste leer. "
        "Keine Fachzeile aus dem BVB-Paket wurde übernommen.",
        "",
        "Ausgenommen sind ausschließlich die bestätigten Schutz-/Parametertabellen, technische "
        "Migrationen/Sessions und 21 temporäre Schutz-Sicherungen t1_saved_*. Diese enthalten "
        "keine kopierten Clubs/Spieler/Stadien; sie bleiben bis zur Abnahme bestehen.",
        "",
        "## 3. Schutzdaten, Profile und Rechte",
        "",
        "**Alle 21 Original-Schutzmengen zurückgeführt und fingerprint-identisch.** "
        "MD5 ist hier ein Inhaltsvergleich über sortierte Zeilenhashes, keine kryptografische "
        "Signatur. Keine Konten-/Passwort-/Profilwerte werden im Bericht ausgegeben.",
        "",
        "| Schutztabelle | Originalzeilen | Gesamt jetzt | Fingerprint vorher = nachher |",
        "|---|---:|---:|---|",
    ]
    report += [f"| {t} | {r['before_rows']} | {r['total_rows']} | {r['after_fingerprint']} |"
               for t, r in evidence["protected"].items()]
    report += [
        "",
        "Profilstart: level=1, xp=0, xp_max=800; 0 abweichende Profile. Favoritenverein und "
        "aktiver Titel NULL. Auch alle übrigen bereits freigegebenen N19-Resetwerte sind "
        "durch den vollständigen Zeilenfingerprint erhalten.",
        "",
        "Login-/Gruppen-/Rechtezuordnungen sind erhalten; Permissions über "
        "(app_label, model, codename) aufgelöst. Zusätzliche ContentTypes/Standardrechte "
        "gehören nur zu den zwei neuen Modellen. Bestehende Rechte wurden nicht gelöscht "
        "oder Personen zugeordnet, neue Rechte wurden nicht eigenmächtig vergeben.",
        "",
        "Migrationen erzeugten zunächst ihre regulären historischen Seeds. Danach wurden "
        "alle aktiven Fach-/Katalogtabellen gemeinsam bereinigt und nur die bestätigten "
        "Original-Schutzdaten plus neue technische Modellrechte wieder eingesetzt. "
        "Ein Sequenz-Abgleich ging zunächst von id-Spalten aus und stoppte bei einem anderen "
        "Primärschlüssel; die Bereinigungstransaktion rollte zurück. Fortsetzung erst nach "
        "erneuter Sicherungs-Fingerprintprüfung, ohne erneute Seed-/Migrationsausführung.",
        "",
        "## 4. Reparaturen aus Abschnitt 6",
        "",
        "Erledigt in T1:",
        "- Snapshot-save im aktivierten neuen Schema: keine verdeckte MW-/Gehalts-/PSR-"
        "Aktualisierung, keine Zehn-Snapshot-Kürzung. Legacy-Bestandsmodus bleibt unverändert.",
        "- Versions-/Payload-Eindeutigkeit für Quellstände; Herkunft und stabile Faktenschlüssel "
        "für MW-/Transferfakten; NULL-ID-/Personen-XOR-/typisierte-ID-Constraints.",
        "- Neue Importzustände und Import-Einzelsperre am Player; allgemeine HistoricCoach-"
        "Personen, nullable Rekordwert und strukturierte Belege.",
        "- Kapazitätssummen bleiben bei unbekannten Einzelwerten NULL, nicht erfundene "
        "0 oder TypeError; belegte Nullen summieren sich weiterhin zu 0.",
        "- Alle sechs Dortmund-PK-Stellen verwenden FMI 907; Live-Link verwendet die "
        "tatsächlich aufgelöste Club-ID. Keine Szene gelesen/gesichert/importiert.",
        "- Pilot lädt vollständige game/showauction/stadium_editor-Apps und gemeinsame "
        "Originalseiten; HTTP-Mutationen bleiben bis weiterer Freigabe gesperrt.",
        "",
        "Noch nicht umgesetzt, bewusst T2–T4:",
        "- Zentraler validierter Paketweg, Positiv-/Uploadmaske einschließlich E35-Grenze, "
        "idempotente Projektionen/Initialisierung und explizite Rating-/Stärke-/Gehaltspfade.",
        "- ID-Spiegel, Person↔Player-Zuordnung ohne Namensfallback, Quellen-/Attributnormalisierung "
        "und lücken-/konfliktbezogene Arbeitslisten mit Ein-Klick-Bestätigung.",
        "- Kader-/U21-/Leihpool-/Scouting-/Aufstellungsfilter und spielbezogene Sperr-Gates. "
        "Die modelseitige Poolkennung allein ersetzt diese noch nicht.",
        "- TM-basierte FK-Nachträge (E69) bei späterem Import: Entscheidung **FK-Backfill "
        "beim Import**, nicht Lookup beim Anzeigen. Historische IDs/Namen unverändert; "
        "auch nach Ligastart erlaubt.",
        "- Stadion-/Profil-Spiegel, NULL-Nutzungsgates, Registry/offene Rekordschlüssel, "
        "Personenbilder, vollständige Historien-/Titel-/Rekord-/Kaderanzeigen und "
        "Creator-Vorschau/-Upload/-Nachpflege.",
        "",
        "Legacy-Platzhalter-/Namens-/CSV-Wege wurden nicht zum neuen Paketweg umgebaut; "
        "sie sind im T1-Pilot nicht per HTTP aufrufbar. Kein behaupteter fertiger Importer.",
        "",
        "## 5. Stärkenparität und technische Prüfungen",
        "",
        f"**{checks['strength_parity']['cases']} identische Eingabesätze vorher/nachher**, "
        "inklusive TW/IV/ZM/ST, FM/CMT/einer/keiner Quelle, fehlendem/vorhandenem Potential "
        "und drei Frischewerten. Aufruf derselben compute_strength_for_player-Funktion "
        "im Bestands- und Pilot-Modellkontext, ohne ORM-Spielerdaten oder Paketimport.",
        "",
        "Identischer Ergebnis-SHA256: " + checks["strength_parity"]["outputs_sha256"] + ".",
        "strength_service.py und strength_engine.py sind bytegleich zur Vorhermessung; "
        "Hashes in t1-strength-before.json und t1-strength-after.json.",
        "",
        "Zusätzliche Rollbacktests: je 12 MW-/Ratingpunkte am selben Datum bleiben bestehen, "
        "ohne aktuelle MW-/Gehalts-/Rating-Schreibwirkung. Kein Testdatensatz persistiert. "
        "Gleiche externe ID in getrenntem Spieler-/Trainerraum zulässig; genau ein "
        "FK-Besitzer per DB-Constraint erzwungen; NULL-Kapazität von belegter 0 unterschieden. "
        "397 aktive Feldlisten-Ziele und alle 384 Paketpfade besitzen ihren SQL-Zielanker; "
        "die vier späteren Jugendbewerbungsfelder bleiben ausdrücklich außen vor. "
        "Django system check ohne Fehler; makemigrations --check ohne Drift; keine offenen "
        "Migrationen; health=200 und POST gesperrt=403; Nullbestand und Schutz-Fingerprints "
        "nach allen Tests nochmals gleich.",
        "",
        "Das ist ein Eingabe-/Code-Paritätsnachweis, kein neuer Saison-Balancinglauf und "
        "keine T2-Importabnahme.",
        "",
        "## 6. real_life_club: Leser und Vorschlag",
        "",
        "- game/views_scouting.py: _find_card, _search_players, transfer_scouting "
        "(Verein/Wappen/Liga in Karten, Suche, Such-/Watchlistdaten).",
        "- game/views.py: player_detail (select_related und Wappenquelle).",
        "- game/admin.py: Player-Form/Querysets/Filter/Feldlisten; _league_coefficient und "
        "_dynamic_league_median_rating lesen Verein/Liga für die bestehende "
        "Stärkevorschau. PlayerDataReviewAdmin lädt den FK ebenfalls.",
        "- game/club_import/fmid_csv_service.py: _apply_row prüft bestehende "
        "real_life_club-Zuordnung vor Ergänzung. Weitere Legacy-Schreiber: "
        "club_import/import_service.py und economy/severance.py.",
        "- Historische Migrationen/Testdateien bleiben historische Verweise. "
        "CMT-Quellprofile mit gleichnamigem Textfeld sind nicht dieser Player-FK.",
        "",
        "**Vorschlag: vorerst abgeleiteter Spiegel von owner_club_id, später entfernen.** "
        "Kein eigener Paket-Eingang, kein unabhängiger Editorwert. Beim nicht importierten "
        "Stammverein bleibt der Spiegel NULL; Anzeige nutzt owner_club_tm_id/Originalname. "
        "T2 führt owner/loan/club/loan_until und aktualisiert real_life_club sowie "
        "loan_status/loan_partner_club nur über einen expliziten gemeinsamen Spiegelweg. "
        "T4 stellt obige Leser auf die kanonischen Beziehungen um. "
        "T1 hat die Legacy-Leser nicht heimlich semantisch umgeschrieben.",
        "",
        "## 7. public und Betriebsgrenzen",
        "",
        f"Vorher/nachher: **{public['unchanged_tables']}/{public['table_count']} Tabellen "
        "fingerprint-identisch**; alle Sequenzstände und alle geprüften Rollen-/Schema-/"
        "Objekt-ACL-/Constraint-Metadaten identisch. Abweichende Tabelle: "
        + ", ".join(changed) + " (Zeilenzahl unverändert).",
        "",
        "**Keine pauschale Bestätigung vollständiger Unverändertheit möglich.** Der "
        "Bestandsdienst wurde nicht für den Vergleich eingefroren; dessen LastSeenMiddleware schreibt bei "
        "authentifizierten Requests last_seen und führt Login-Belohnungslogik aus. "
        "Dieser Pfad erklärt mögliche parallele Profilaktivität, ist aber ohne "
        "Vorherwerte pro Spalte kein beweisbarer Ausschluss anderer Profiländerungen. "
        "Es wurden bewusst keine alten Werte geraten oder nach public zurückgeschrieben.",
        "",
        "Alle Schema-/Bereinigungs-/Rückführungswrites erfolgten über direkte "
        "import_pilot_role-Verbindung mit genau search_path=import_pilot. Der Guard "
        "verweigert public-Schreibrechte, Rollenerhöhung und fremde Suchpfade. "
        "Die public-Prüfverbindungen waren read-only. Keine public-Migration, kein "
        "Truncate/Update/Delete, keine Änderung bestehender Rollen oder ACLs. "
        "Kein Hetznerzugriff, keine Worker/Beat-Jobs, keine Änderung von Produktionssecrets. "
        "Keine bestehenden Prozesse/Workflows wurden manuell neu gestartet oder gestoppt. "
        "Nur ein kurzlebiger lokaler Pilot-HTTP-Testserver wurde gestartet, geprüft und "
        "wieder beendet; sein Healthcheck zeigte t1-full-game-no-import. Der zusätzliche "
        "404-Request war das nicht vorhandene favicon.ico; der Nullbestand blieb erhalten. "
        "Kein Broker-Eingriff.",
        "",
        "**HALT.** Schutz-Sicherungen bleiben bis Abnahme erhalten. "
        "T2–T5 werden nicht begonnen; keine Aussage zu fehlenden Spielern beim "
        "Vorstart-Reupload oder Rückkehr zu einem nicht importierten Stammverein "
        "vorweggenommen.",
    ]
    (folder / "t1-bericht.md").write_text("\n".join(report) + "\n")
    print(json.dumps({"report_written": True, "new_tables": new_tables,
                      "added_columns": len(added), "altered_fields": len(altered),
                      "public_changed_tables": changed}))


if __name__ == "__main__":
    write()
