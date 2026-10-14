"""Build a review-only handoff, excluding private database backups and sessions."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/augsburg-v2-korrektur"


def main(source):
    package = OUT / "paket/augsburg"
    if package.exists():
        raise ValueError("Paket-Ausgabe besteht bereits; nicht still überschreiben.")
    shutil.copytree(source, package)
    current = package / "werkzeuge/render/static_replit_korrigiert"
    shutil.copytree(source / "werkzeuge/render/static_replit", current)
    modules = ROOT / "stadium_editor/static/stadium_editor"
    for name in ("unity_stadium_scene.js", "dortmund_surroundings.js", "surroundings_ground.js"):
        shutil.copy2(modules / name, current / "stadium_editor" / name)
    document = ROOT / "docs/stadionpakete/ANWEISUNG_FUER_CLAUDE_NACH_AUGSBURG_V2.md"
    shutil.copy2(document, package / document.name)
    shutil.copy2(OUT / "presentation_replit_korrigiert.json",
                 package / "werkzeuge/render/presentation_replit_korrigiert.json")
    pictures = package / "bilder/replit-korrektur"
    shutil.copytree(OUT / "ansichten", pictures)
    shutil.copy2(OUT / "augsburg-v2-korrektur-ansichten.jpg", pictures)
    shutil.copy2(OUT / "render-evidence.json", pictures)
    (package / "KORREKTUR-REPLIT.md").write_text(
        "# Verbindlicher Replit-Korrekturstand nach Augsburg V2\n\n"
        "Dieser Nachtrag, die neue Claude-Anweisung und bilder/replit-korrektur "
        "definieren den aktuellen Stand. Frühere Mock-Ziele und Dokumente mit "
        "Status »Gelände offen« sind historische Belege.\n\n"
        "- Gemeinsame Geländefunktion implementiert und mit aktuellen Projektmodulen geprüft.\n"
        "- Lokal NORD/WEST/OST; 30.660 Plätze, Stehplätze NORD 5.366 / SUED 1.150, "
        "Vereins-/Stadiondaten, Blöcke, Designs und Ausbauten unverändert.\n"
        "- Nur surroundings.groundLevel=7.7 und die geprüfte 36-Punkt-Umlaufplatten-Hülle "
        "als surroundings.groundCutout ergänzt. Alle Originalpolygone erhalten.\n"
        "- Vollständiger Bestand: 26 Gebäude, 189 Straßen, 47 Grünflächen, kein Wasser. "
        "Nur green[3] beim Rendern innerhalb des Lochs ausgelassen; keine Datenlöschung.\n"
        "- Grundboden bei 7,35 m; Umlauf bei ca. 7,7–7,72 m. Kein erfundenes Relief.\n"
        "- Kritische Überschneidungen führen zum Abbruch, keine automatische Gebäude-/Straßenfilterung.\n"
        "- V2-Modellassets und Manifestkopien unverändert: 7718595a38dc4253. "
        "Dachpräfix DACH_ (59 Meshes), 96.252 Dreiecke, Lichtfaktor 1.\n"
        "- Neun neue Software-WebGL-Ansichten, keine Seitenfehler; "
        "nicht die alten Mock-Aufnahmen als neuen Nachweis verwenden.\n"
        "- Vorschau: werkzeuge/render/presentation_replit_korrigiert.json, "
        "Module: werkzeuge/render/static_replit_korrigiert/. "
        "Harness-Parameter r=static_replit_korrigiert&p=presentation_replit_korrigiert.json; "
        "Modellroute /models/2238/7718595a38dc4253/ muss auf die Paketassets zeigen.\n"
        "- Keine privaten Backups im Paket. Keine Registrierung, kein Upload, "
        "keine externe Übertragung, keine Veröffentlichung.\n"
        "- Original-Unity-Bundle fehlt in Replit; Binaryprüfung ist keine Originalextraktion.\n",
        encoding="utf-8",
    )
    checks = []
    for file in sorted(package.rglob("*")):
        if file.is_file() and file.name != "PRUEFSUMMEN.sha256":
            checks.append(f"{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.relative_to(package).as_posix()}")
    (package / "PRUEFSUMMEN.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")
    manifest = json.loads((package / "models/2238.json").read_text())
    asset_dir = package / "stadium-models/2238" / manifest["assetVersion"]
    assert (package / "models/2238.json").read_bytes() == (asset_dir / "manifest.json").read_bytes()
    for name, digest in manifest["assetSha256"].items():
        assert hashlib.sha256((asset_dir / name).read_bytes()).hexdigest() == digest
    target = OUT / "stadionpaket-2238-v2-replit-korrigiert.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(package.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(package.parent).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert not any("db-before" in n or "db-after" in n or "session" in n for n in archive.namelist())
        for line in checks:
            digest, name = line.split("  ", 1)
            assert hashlib.sha256(archive.read("augsburg/" + name)).hexdigest() == digest
    print(json.dumps({"zip": str(target.relative_to(ROOT)), "bytes": target.stat().st_size,
                      "checksums": len(checks), "assets": len(manifest["assetSha256"]),
                      "integrity": "passed"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    main(parser.parse_args().source)
