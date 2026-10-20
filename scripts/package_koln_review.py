"""Package actual Cologne renders and installation evidence for review."""
import base64
import html
import json

from PIL import Image, ImageDraw

from scripts.package_mainz_review import font
from scripts.prepare_koln_study import OUT


def main():
    review = OUT / "osm-fresh"
    read = lambda name: json.loads((review / name).read_text())
    check, evidence = read("integration-check.json"), read("evidence.json")
    assert check["registered"] and check["integrated"] and check["stadiumAndDesignUnchanged"]
    renders = read("ansichten/render-evidence.json")
    installed = read("installed-views/render-evidence.json")
    assert len(renders) == 7 and len(installed) == 2
    assert all(not r["errors"] and r["assetVersion"] == check["assetVersion"]
               for r in renders + installed)
    unique = {key: len({r["osm"] for r in rows})
              for key, rows in evidence["features"].items()}
    views = [
        ("ansichten/editor-dach-an.png", "Originalmodell und OSM-Umfeld · Dach an"),
        ("ansichten/editor-dach-aus.png", "Dach aus · Ränge und Pylone bleiben erhalten"),
        ("installed-views/ticker-tag.png", "Registrierte Spielansicht · Tag"),
        ("installed-views/ticker-nacht-flutlicht.png", "Registrierte Spielansicht · Nacht und Flutlicht"),
    ]
    sheet = Image.new("RGB", (1440, 1050), "#071018")
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 18), "KÖLN · RHEINENERGIESTADION", font=font(30), fill="white")
    draw.text((24, 63), "Registriert und eingebaut · Kapazität unverändert 50.000",
              font=font(20), fill="#6bdcb1")
    panels = []
    for i, (name, title) in enumerate(views):
        path = review / name
        original = Image.open(path).convert("RGB")
        original.thumbnail((700, 394), Image.Resampling.LANCZOS)
        x, y = 13 + (i % 2)*714, 110 + (i // 2)*440
        sheet.paste(original, (x, y))
        draw.text((x+4, y+400), title, font=font(18), fill="#d0e2eb")
        panels.append(f'<figure><img alt="{html.escape(title)}" src="data:image/png;base64,'
                      f'{base64.b64encode(path.read_bytes()).decode()}">'
                      f'<figcaption>{html.escape(title)}</figcaption></figure>')
    draw.text((24, 1004), "© OpenStreetMap contributors · ODbL · Gelände eben; Höhen teilweise schematisch",
              font=font(17), fill="#b9cdd6")
    sheet.save(review / "koln-eingebaut.jpg", quality=91)
    report = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Köln · Einbauprüfung</title>
<style>body{{font:16px system-ui;background:#071018;color:#dfebf3;max-width:1450px;margin:30px auto;padding:0 24px}}
aside{{padding:18px;background:#11232a;border-left:3px solid #6bdcb1}}
section{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:24px}}
figure{{margin:0}}img{{width:100%}}figcaption{{padding:10px 0}}a{{color:#6bd4ed}}</style>
<h1>Köln · RheinEnergieSTADION eingebaut</h1>
<aside>Originalmodell registriert, 103 Browserassets dauerhaft gespeichert und mit SHA-256 rückgeprüft.
Kapazität unverändert 50.000; Stadionwerte, Manager-Ausbau und gespeicherte Entwürfe unverändert.
Workspace-Einbau, kein Produktions-Deployment.</aside>
<p>304 Quellmeshes, 51 gezielt schaltbare Dachmeshes. Feldlinien 105 × 68 m.
46.424 Sitzpunkte passen zu acht Crowd-Bereichen; sie bestimmen nicht die Spielkapazität.
Zwölf tatsächliche Lichtpositionen aus 64 geprüften Unity-Spotlights.
Sieben Quellrenderings und zwei zusätzliche Renderings über die registrierten
Anwendungs-Asset-Endpunkte ohne Seitenfehler.</p>
<p>Frischer OSM-Auszug: {unique['buildings']} Gebäudeobjekte,
{unique['roads']} Straßen-/Wegeobjekte, {unique['trees']} kartierte Bäume,
{unique['green']} Grünobjekte und {unique['water']} Wasserobjekte.
Kein zusätzliches OSM-Stadiongebäude, keine OSM-Flächen am Stadion abgeschnitten,
keine Grün-/Wasserflächen vom Renderer ausgelassen.
Gemeinsame Geländeprüfung ohne Befunde.</p>
<section>{''.join(panels)}</section>
<h2>Offengelegte Grenzen</h2><ul>
<li>Flaches Gelände, kein vermessenes DEM. Gebäudehöhen und Baumkronen teilweise schematisch.</li>
<li>Drei unvollständige OSM-Multipolygon-Grenzen im Kartenausschnitt.</li>
<li>Die 33 Editor-Hüllen stammen aus den Sitzquellgruppen; sie sind keine offiziellen
nummerierten Stadionblöcke. Die 3D-Crowd-Geometrie bleibt original.</li>
<li>Unity-Shader und gebackene Lightmaps/Probes werden nicht vollständig nachgebildet.</li>
</ul><p>© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, ODbL.
Richtungsabgleich mit dem <a href="https://fc.de/club/ueber-den-fc/spiel-und-trainingsstaette/rheinenergiestadion">
offiziellen FC-Stadionplan</a>: Heimkurve Süd, Gäste Nord/Ost.</p></html>"""
    (review / "koln-einbaupruefung.html").write_text(report)
    print(json.dumps({"installed": check, "distinctOsmObjects": unique,
                      "sourceCaptures": len(renders), "installedCaptures": len(installed)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
