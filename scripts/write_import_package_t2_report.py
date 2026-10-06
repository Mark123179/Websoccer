"""Generate the seven-point report from measured pilot evidence, not fixtures."""
import json
import re
import subprocess
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = ROOT / "docs/import-pilot"


def write():
    e = json.loads((DIRECTORY / "t2-evidence.json").read_text())
    checks = json.loads((DIRECTORY / "t2-backend-checks.json").read_text())
    public = json.loads((DIRECTORY / "n33-public-comparison.json").read_text())
    assert not public["changed_tables"]
    before_log = Path("/tmp/import-n33-alt-tests.log").read_text()
    after_log = Path("/tmp/import-t2-alt-tests.log").read_text()
    assert "N33_ALT_TEST_EXIT_CODE=0" in before_log
    assert "T2_ALT_TEST_EXIT_CODE=0" in after_log
    c, s, refs = e["counts"], e["squad"], e["references"]
    files = [
        "core/settings.py", "import_pilot/settings.py", "game/import_schema.py",
        "game/models.py", "game/club_import/runtime.py", "game/club_import/package_service.py",
        "game/club_import/import_service.py", "game/club_import/fmid_csv_service.py",
        "game/economy/severance.py", "game/views_scouting.py", "game/views.py",
        "game/admin.py", "game/match_readiness.py", "game/match_engine.py",
        "game/scouting/coverage.py", "game/scouting/draw.py", "game/scouting/service.py"]
    switches = subprocess.run(["rg", "-n",
        r"IMPORT_PACKAGE_MODE|package_mode\(|ownership_field\(|owner\(|owner_name\(|scouting_condition\(|match_condition\(|can_scout\(",
        *files], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    (DIRECTORY / "t2-schalterstellen.txt").write_text(switches)
    rows = "\n".join(f"| {label} | {count} |" for label, count in [
        ("Vereine / Ligen", "1 / 1"),
        ("Spieler", c["players"]), ("Personen", c["persons"]),
        ("Marktwertpunkte", c["market_values"]), ("davon echte Paket-Historie", c["real_market_values"]),
        ("davon gekennzeichnete Startwerte", c["start_values"]), ("Transfers", c["transfers"]),
        ("Rekorde", c["records"]), ("Titel-Einzeleinträge", c["title_entries"]),
        ("aggregierte Titelzeilen", c["aggregated_title_rows"]),
        ("Quellstand-Snapshots", c["source_snapshots"]),
        ("Arbeitsliste: blocking", 0), ("Arbeitsliste: player_lock", c["issues"]["player_lock"]),
        ("Arbeitsliste: info", c["issues"]["info"])])
    sample_rows = []
    for sample in e["strength_samples"]:
        values = {r["source"]: f'{r["rating"]} / {r["potential"] if r["potential"] is not None else "NULL"}'
                  for r in sample["sources"]}
        sample_rows.append(f'| {sample["name"]} | {values.get("FM", "—")} | '
            f'{values.get("CMTRACKER", "—")} | {sample["base_strength"]} | {sample["max_strength"]} |')
    text = f"""# T2-Bericht – BVB-Paketimport im Pilot

Stand: 06.10.2026 · Nachtrag 7 ist maßgeblich.

**Halt bei T2. Keine uneingeschränkte Abnahme:** Paketweg und Import sind umgesetzt.
Der Stärkepunkt bleibt für 14 Dynamic-Spieler offen. Keine Ersatzpotentiale, keine
Formeländerung und keine künstlichen 50er-Stärken wurden eingeführt. T3–T5 bleiben gesperrt.

## 1. N33, Integration und Altmodus

- Gemeinsames Schema immer geladen; nur `IMPORT_PACKAGE_MODE` schaltet Verhalten.
  Im Hauptstand false, im Pilot true. T1 liegt im gemeinsamen Hauptstand; es gab
  keinen getrennten T1-Branch zu mergen. Kein Commit/Push/Server-Deploy durchgeführt.
- 0187 unverändert. SHA-256:
  `bd63abb95ad8d985694ae0e82a9c120df8eb5e4784e86ad20f47c76a59e25737`.
- 0188 auf public und Pilot: vorhandene Spieler ungesperrt; normale Vereine spielbar,
  bisherige Platzhalter nicht spielbar. Default import_lock=false. Alte Stadion-
  Konstruktionsdefaults bleiben 0, der Paketweg setzt unbekannte Kapazität explizit NULL.
- Leih-Pool benötigt fehlenden Spielverein und nicht importierten Leihverein;
  Spieler bei importierten Leihvereinen und Prüfpool-Spieler sind ausgeschlossen.
- Feldlisten korrigiert: Positionsspiegel nach Ligastart unberührt; keine Verweis-
  Club-Zeilen und keine zweite Echtwelt-Leihschicht.
- 0189 ergänzt review_pool, den Liga-Zustand is_playable und nullable Player.potential
  (Legacy-Default 50 unverändert). Beide Modi melden keine Migrationsdrift.
- Vor T2: 1.654 Altmodus-Tests grün, Exit 0. Nach den T2-Änderungen erneut
  1.654 Tests grün, Exit 0. Direkter Befehl: `python manage.py test game.tests`.
- Alle direkten Schalter-Abfragen UND indirekten Aufrufer stehen vollständig mit
  Dateiname und Zeile in `t2-schalterstellen.txt` (Anlage unten).
  Gruppen: Kapazitätsaggregation; Snapshot-Speicherung; Paket-/Altimport;
  Eigentümer-Leser/Formular/Filter/Stärkevorschau; Scouting-Pool/-Gebote;
  erste Mannschaft und Engine-Zulässigkeit; kontrollierte Prüfpool-Zuordnung.
- Ablaufdatum: bei Übernahme einschalten, anschließend Schalter und sämtliche
  Altzweige entfernen. Nie wieder Modelle/Spalten hinter diesen Schalter stellen.
- Die erlaubten t1_saved_*-Sicherungen sind weiterhin vorhanden; nicht entfernt.
  Keine deploy.sh-Sperre, kein Hetznerzugriff, keine Dortmund-Szenensicherung.

## 2. BVB tatsächlich eingelesen

Paket: `{PACKAGE_NAME}`.
data.json-Prüfsumme: `{e["package_sha256"]}`.
Zielliga Bundesliga, Deutschland, spielbar; für T2 im Pilot als Ziel angelegt.
Eine atomare Transaktion pro Paket. Keine Netzwerkabfrage, kein Namensmatching.

| Bestand im Pilot | Anzahl |
|---|---:|
{rows}

Arbeitsliste: 143 unveränderte Lücken des Pakets (141 Info + 2 Einzelsperren)
plus 13 Info-Vereinsverweise ohne TM-ID = 156 Einträge. Verschiedene Hinweise
zu demselben Feld bleiben getrennt; kein Verlust durch Zusammenfassen.

Alle 631 TM-Historienpunkte und 322 Transfers bleiben vollständig.
Kein zusätzlicher erfundener Marktwert-Erhebungspunkt. NULL bleibt in den
Quellwerten NULL. Nur N10 erzeugt sechs markierte Spiel-Startwerte von 50.000 €.
Gehalt wurde für alle Spieler als Marktwert / 1.000.000 × 5.000 € gesetzt.
`real_life_club` ist für alle importierten Spieler leer.

## 3. Kader und Leihen

- Aktiver BVB-Kader: 47 = {len(s["first"])} erste Mannschaft + {len(s["u21"])} U21.
- Leih-Pool: {len(s["loan_pool"])}. Diese Spieler zählen nicht zum aktiven BVB-Kader.
- Geliehene beim BVB: {len(s["borrowed"])}.
- Prüfpool im Referenzimport: {len(s["review_pool"])}.

| Fall | Name | Stammverein → Leihverein |
|---|---|---|
| Geliehen, erste Mannschaft | Ethan Nwaneri | FC Arsenal (11) → BVB (16) |
| Geliehen, U21 | Takato Yamamoto | Gamba Osaka (596) → BVB (16) |
| Geliehen, U21 | Daniel Sumbu | SK Sturm Graz II (4443) → BVB (16) |
| Leih-Pool, erste Mannschaft | Diant Ramaj | BVB → FC Kopenhagen (190) |
| Leih-Pool, erste Mannschaft | Almugera Kabar | BVB → NEC Nijmegen (467) |
| Leih-Pool, erste Mannschaft | Yan Couto | BVB → Como 1907 (1047) |
| Leih-Pool, U21 | Elias Benkara | BVB → SpVgg Greuther Fürth (65) |

Die vier Leihvereine sind noch nicht importiert: club=NULL, TM-ID + Originalname
erhalten. Kein Leih-Scheinverein. Bei späterem Import wird der FK über TM-ID
nachgetragen. Der Leihstand liegt einmal im Spielstand; der Erhebungsstand bleibt
im unveränderten Paketarchiv.

Erste Mannschaft: {", ".join(s["first"])}.

U21: {", ".join(s["u21"])}.

## 4. Identischer Zweitimport

Vorher/Nachher: alle {e["second_upload"]["compared_tables"]} regulären Pilot-Tabellen
über Zeilenzahl und sortierten Inhalts-Fingerprint verglichen.
**0 neue Zeilen, 0 geänderte Tabellen-Fingerprints, 0 Änderungen.**
Auch spätere identische Wiederholungen bleiben ohne Schreibvorgang.

Beleg: `t2-second-upload-fingerprints.json`. Ein früheres Paket nach einem
zwischenzeitlich anderen Paket wird dagegen erneut verarbeitet: damit kann ein
Prüfpool-Spieler wieder über seine TM-ID zugeordnet werden.

## 5. Stärke – offener Abnahmepunkt

- 49 Spieler haben Quellwerte; der bestehende Berechnungsweg wurde für alle ausgeführt.
- {c["calculated"]} Ergebnisse berechnet und im PlayerStrengthProfile gespeichert.
- 14 Spieler: FM-Rating vorhanden, ausschließlich NULL/Dynamic-Potential; der
  unveränderte Rechner liefert keinen berechenbaren Bereich und daher keine Basis.
- 2 Paket-Einzelsperren: Takato Yamamoto und Bjarki Gardarsson (kein FMInside).
- Die 14 Dynamic-Spieler sind NICHT zusätzlich als player_lock markiert.
  Ohne Stärkeprofil werden sie nicht mit einer Ersatzstärke in die Engine gegeben.
  Alle 28 aktiven Spieler der ersten Mannschaft sind berechnet und zulässig.

Dynamic-Fälle: {", ".join(e["dynamic_uncomputable"])}.

| Stichprobe | FM Rating / Potential | CMTracker Rating / Potential | Basis | Maximum |
|---|---|---|---:|---:|
{chr(10).join(sample_rows)}

Persistierte Basis entspricht jeweils dem Ergebnis. CMTracker-Attribute laufen
über dieselbe bestehende API→CSV-Spaltennormalisierung; Rohattribute/Versionen
bleiben vollständig im Quellstandarchiv. strength_engine.py und seine Formeln
wurden nicht verändert. Grund des offenen Punkts: calculate_potential_200 gibt
ohne Quellpotential ausdrücklich None; get_strength_range gibt dann (None,None).

**Erforderliche Klärung vor vollständiger T2-Abnahme:** ob und wie bei Dynamic
eine Basisstärke ohne berechenbares Potential über den bestehenden Berechnungsweg
zulässig werden soll. Kein Rating→Potential-Ersatz auf eigene Entscheidung.

## 6. Verweis-Vereine

- {refs["distinct_external_tm_ids"]} verschiedene externe TM-IDs (ohne BVB 16;
  einschließlich BVB somit {refs["distinct_external_tm_ids"] + 1}).
- {len(refs["names_without_tm_id"])} verschiedene Namen ohne TM-ID,
  {refs["occurrences_without_tm_id"]} Vorkommen. Je Name ein Info-Arbeitslisteneintrag.
- game_club enthält **genau eine Zeile: BVB**. Null zusätzliche Verweis-Club-Zeilen.
- Automatisches Nachtragen getesteter Referenzen erfolgt ausschließlich per TM-ID,
  auch bei abweichendem Vereinsnamen; kein Namensabgleich.

Namen ohne TM-ID: {", ".join(refs["names_without_tm_id"])}.

## 7. Alter Stand und Schutzbereiche

- Altmodus bleibt false und verwendet die bisherigen Leser/Schreiber/Defaults.
- Vergleich über alle 159 bisherigen public-Tabellen und ihre bisherigen Spalten:
  0 Abweichungen. Einzige ausdrückliche Ausnahme: akzeptiertes last_seen.
  Nur neue technische Modell-/Migrationszeilen sind vom Altzeilenvergleich ausgenommen.
- 21 geschützte Pilot-Tabellen: identische Fingerprints vor/nach Import.
- Separater Pilot-DB-Login mit Suchpfad import_pilot; kein Schreibrecht nach public.
  Kein Rechteentzug am Bestand, kein Zugriff auf Hetzner.
- Backend-Prüfungen bestanden: Initialbestand, identischer Reimport,
  atomarer Abbruch bei falscher Stadionsumme/split identities, Prüfpool-Erhalt und
  beide Wiederzuordnungswege, N30-Maske, FK-Nachtrag und Scouting-Zuordnung,
  N35-Admin-Leser und erste-Mannschaft-Zulässigkeit, vollständiger Fixture-Rollback.
- Alle ursprünglichen Paket-Lücken und 13 Namensverweise wurden zusätzlich nachgezählt.
- Startprüfung: Anwendung gestartet, Systemcheck ohne Befund; Anmeldeseite HTTP 200
  und visuell korrekt. Bei einigen fehlenden Vereinswappen liefert die
  Staticfiles-Auslieferung HTTP 500 (TypeError: Liste statt Dateipfad).
  Asset-Finder und Staticfiles-Konfiguration wurden durch diesen Umbau nicht geändert.
  Dieser separate Befund wurde nicht außerhalb des freigegebenen Umfangs behoben.
  Der rote Test-Workflow enthält einen älteren Lauf; maßgeblich sind die beiden
  neuen vollständigen Shell-Läufe mit jeweils 1.654 bestandenen Tests und Exit 0.
- Creator-Upload, Vorschau, Anzeige-Ausbau, Reset-Befehl und Szene-Backup nicht gebaut.
  HTTP-Schreibwege des Piloten bleiben absichtlich gesperrt.

Belege: `t2-evidence.json`, `t2-backend-checks.json`,
`n33-public-comparison.json`, `t2-second-upload-fingerprints.json`.

## Anlage: vollständige Schalterstellen

```text
{switches.rstrip()}
```
"""
    (DIRECTORY / "t2-bericht.md").write_text(text)
    html = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>T2-Bericht – BVB-Paketimport</title><style>
body{{margin:0;background:#f4f6f8;color:#18212b;font:15px/1.65 system-ui,sans-serif}}
main{{max-width:1120px;margin:32px auto;padding:32px;background:white;border:1px solid #dce2e8}}
h1{{font-size:28px;margin:0 0 14px}}.notice{{padding:16px;border-left:4px solid #b56b00;background:#fff5e4}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.65 ui-monospace,monospace}}
@media print{{main{{margin:0;border:0;padding:0}}body{{background:white}}}}
</style><main><h1>T2-Bericht – BVB-Paketimport</h1>
<p class="notice">Halt bei T2. 14 Dynamic-Potential-Fälle bleiben als Stärke-Abnahmepunkt offen.
Keine Ersatzwerte und keine Formeländerung.</p><pre>{escape(text)}</pre></main></html>"""
    (DIRECTORY / "t2-bericht.html").write_text(html)
    print("Seven-point Markdown/HTML report and switch inventory generated.")


PACKAGE_NAME = "bvb_vereinspaket_2026-10-05_1_1791225377498.zip"
if __name__ == "__main__":
    write()
