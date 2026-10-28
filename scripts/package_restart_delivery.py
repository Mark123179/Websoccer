"""Package only verified facts/evidence, never scratch databases or credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.directory)
    report = json.loads((root / "complete-parity.json").read_text())
    manifest = json.loads((root / "complete-manifest.json").read_text())
    if (not report["all_tables_identical"] or not report["schema_identical"]
            or manifest["blockers"] or not manifest["assembly"]["baseline_preservation"][
                "all_current_baseline_facts_preserved"]):
        raise ValueError("Nur vollständig geprüfte Übergaben dürfen verpackt werden.")
    payload = (root / "complete-current-state.zip").read_bytes()
    if checksum(payload) != report["package_sha256"]:
        raise ValueError("Übernahmepaket wurde nach der Prüfung verändert.")
    source = Path(manifest["assembly"]["swiss_projection"]["original_archive"]).read_bytes()
    if checksum(source) != manifest["assembly"]["swiss_original_sha256"]:
        raise ValueError("Schweizer Original stimmt nicht mit dem geprüften Beleg überein.")
    summary = manifest["inventory"]["summary"]
    rows = "\n".join(
        f"| {name} | {value['rows']} | {value['sha256']} |"
        for name, value in manifest["parity"].items())
    readme = f"""# Vollständiges Übernahmepaket – geprüfter Datenstand

**Kein Live-Zugriff, kein Reset, kein Produktionsimport, keine Ausführungsfreigabe.**

Der Workspace enthielt 94 Vereine aus fünf Ligen. Ausschließlich auf einer
isolierten Prüfkopie wurden die zwölf freigegebenen Schweizer Vereine ergänzt.
Das kombinierte Paket enthält {summary['clubs']} Vereine, {summary['players']} Spieler,
{summary['market_value_points']} Marktwertpunkte und
{summary['transfer_history_rows']} Transferhistorienzeilen.

`complete-current-state.zip` ist der maßgebliche aktuelle Datenbestand.
`sources/swiss-original.zip` und archivierte Paket-JSONs sind nur Quellenbelege,
nicht anstelle des aktuellen Stands erneut einzuspielen.

Alle 25 freigegebenen Tabellen wurden in eine zweite leere isolierte Datenbank
mit neu erzeugten IDs übertragen und feldweise verglichen. Die Baseline wurde
gegen ältere überlappende Schweizer Quelldaten geschützt. Manuelle FM-IDs,
NULL-Potenziale, Sperren, Nachwuchskader, Ratings und Stärkeprofile bleiben
erhalten. Nur zuvor fehlende Quellvereins-Verknüpfungen wurden aufgelöst.

Schweizer Rekordkorrekturen sind enthalten: GC 1:8 gegen Basel und Vogels
Ligadebüt; Luzern/Sion jeweils 16 ohne Sieg; Zürichs ungeschlagene Serie und
Lausannes Trainer-Siegesserie bleiben ausdrücklich offen. Koné und Kristal
bleiben Manchester United bzw. Köln zugeordnet, mit Leihzielen Lausanne/Thun.

Keine Konten, Bilddateien, Workspace-PK-Referenzen, Spielkontostände, persönlichen
Stadionentwürfe oder Datenbankdumps. Das Schweizer Originalarchiv enthält
ausschließlich die erneut gelieferte, prüfsummengleiche Quelldatei.

Paket-SHA-256: `{report['package_sha256']}`
Kanonischer Tabelleninhalt: `{report['content_sha256']}`

## Inhalt

- complete-current-state.zip: aktueller Übernahmeinhalt + archivierte Provenienz
- evidence/complete-parity.json: Struktur-, Zeilen- und Inhaltsvergleich
- evidence/complete-manifest.json: Umfang, Feldschema, Ausschlüsse und Quellen
- evidence/baseline-preservation.json: Erhalt aller aktuellen Baseline-Fakten
- evidence/swiss-source-projection.json: Original-/Projektionsvergleich
- evidence/base-parity.json: Nachweis des eigenständigen Workspace-Basisübertrags
- evidence/targeted-tests.log: 25 erfolgreiche gezielte Schutz-/Quellentests
- sources/swiss-original.zip: bytegleiches Original, keine automatische Anwendung
- SHA256SUMS: Prüfsummen aller gelieferten Dateien

## Struktur und Grenzen

Feldtypen, NULL-Eigenschaften, Präzision, Länge und Relationsziele der
freigegebenen Spalten sind geprüft; ebenfalls die Fremdschlüssel. Zeitstempel
behalten sämtliche Mikrosekundenstellen. Die Parität gilt für diese
Positivliste, nicht für ausgeschlossene Spieldaten.

Dies ist ein SQLite-Prüftransport, keine PostgreSQL-Serverwiederherstellung.
Die allgemeinen Test-, Sicherheits- und Datenqualitätsworkflows waren beim
Abruf nicht vollständig grün. Ihre Sanierung, private Live-Sicherungen,
Server-Wiederherstellung und eine konkrete Reset-Freigabe bleiben separate
Voraussetzungen. `full_restart_ready=false` ist absichtlich gesetzt.

Im Codeprojekt dokumentiert:
docs/import-pilot/live-neustart-uebernahmepaket-2026-10-28.md
Reproduktion: scripts/assemble_live_restart_handoff.py und
core.live_restart_verify_settings. Der Prüfbefehl verweigert normale
Workspace-Einstellungen, PostgreSQL und schon befüllte Prüfdateien.

## Tabellenparität

| Tabelle | Zeilen | Kanonischer SHA-256 |
| --- | ---: | --- |
{rows}
"""
    files = {
        "README.md": readme.encode(),
        "complete-current-state.zip": payload,
        "sources/swiss-original.zip": source,
    }
    for name in (
        "complete-parity.json", "complete-manifest.json", "baseline-preservation.json",
        "swiss-source-projection.json", "base-parity.json",
    ):
        files[f"evidence/{name}"] = (root / name).read_bytes()
    files["evidence/targeted-tests.log"] = (
        root.parent / "targeted-tests-complete.log").read_bytes()
    files["SHA256SUMS"] = "".join(
        f"{checksum(data)}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    (root / "README.md").write_text(readme)
    print(json.dumps({
        "file": str(output), "bytes": output.stat().st_size,
        "sha256": checksum(output.read_bytes()),
    }, indent=2))


if __name__ == "__main__":
    main()
