"""Present the isolated Mainz review honestly; no live-editor claim or source cleanup."""
import base64
import html
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/mainz-study"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default(size=size)


def main():
    source = json.loads((OUT / "osm-source.json").read_text())
    review = json.loads((OUT / "review.json").read_text())
    manifest = json.loads((OUT / "manifest.json").read_text())
    evidence = json.loads((OUT / "render-evidence.json").read_text())
    assert len(evidence) == 5 and all(
        row["assetVersion"] == manifest["assetVersion"] and not row["errors"]
        for row in evidence
    ), "All five current-version browser captures must finish first."
    reference = Image.new("RGB", (1200, 675), "#0b151b")
    draw = ImageDraw.Draw(reference)
    outline = source["outline"]
    center = source["meta"]["fieldC"]
    scale = 2.2
    def point(p):
        return (600 + (p[0] - center[0]) * scale, 340 + (p[1] - center[1]) * scale)
    draw.polygon([point(p) for p in outline], fill="#273943", outline="#5d7584")
    for block in source["blocks"]:
        draw.polygon([point(p) for p in block["quad"]], fill="#a31e36", outline="#0d1d25")
    theta = source["meta"]["axisTheta"]
    def field(u, v):
        return point((center[0] + u * math.cos(theta) - v * math.sin(theta),
                      center[1] + u * math.sin(theta) + v * math.cos(theta)))
    draw.polygon([field(u, v) for u, v in [(-52.5,-34),(52.5,-34),(52.5,34),(-52.5,34)]],
                 fill="#345e37", outline="#ecf2ee", width=2)
    draw.line([field(0,-34),field(0,34)],fill="white",width=2)
    draw.text((34, 24), "MAINZ · 2D-QUELLGRUNDRISS", font=font(26), fill="white")
    draw.text((34, 61), "Vorhandene Blaupause; kein installierter Editor und keine neue Platzzuteilung",
              font=font(17), fill="#bbc9d2")
    draw.text((34, 630), f"Lokal: {review['capacityFromDatabase']:,} Plätze · Spielfeld: 105 × 68 m".replace(",", "."),
              font=font(20), fill="#d3dce4")
    reference.save(OUT / "ansichten/2d-quellgrundriss.png")
    views = [
        ("2d-quellgrundriss", "2D-Quellgrundriss · noch nicht als Editor eingebaut"),
        ("3d-editor-dach-an", "Originalmodell · Dach an"),
        ("3d-editor-dach-aus", "Originalmodell · Dach aus"),
        ("ticker-tag-dach-an", "Gemeinsame Spielkamera · Tag mit Dach"),
        ("ticker-tag-dach-aus", "Gemeinsame Spielkamera · Tag ohne Dach"),
        ("ticker-nacht-flutlicht", "Gemeinsame Spielkamera · Nacht mit Flutlicht"),
    ]
    sheet = Image.new("RGB", (1440, 1405), "#071018")
    d = ImageDraw.Draw(sheet)
    d.text((26, 16), "MEWA ARENA · ERSTE ISOLIERTE MODELLPRÜFUNG", font=font(28), fill="white")
    d.text((26, 57), "Geografisches Umfeld noch blockiert · nicht registriert · keine Spieldaten geändert",
           font=font(18), fill="#f0c780")
    panels = []
    for i, (name, title) in enumerate(views):
        file = OUT / "ansichten" / f"{name}.png"
        im = Image.open(file).convert("RGB").resize((700, 394), Image.Resampling.LANCZOS)
        x, y = 13 + (i % 2) * 714, 99 + (i // 2) * 433
        sheet.paste(im, (x, y))
        d.text((x+8,y+400),title,font=font(18),fill="#d9e4eb")
        encoded = base64.b64encode(file.read_bytes()).decode()
        panels.append(f'<figure><img src="data:image/png;base64,{encoded}" alt="{html.escape(title)}">'
                      f'<figcaption>{html.escape(title)}</figcaption></figure>')
    sheet.save(OUT / "mainz-erste-modellpruefung.jpg", quality=90)
    report = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mainz · Modellprüfung</title>
<style>body{{background:#081018;color:#e3edf4;font:16px system-ui;max-width:1400px;margin:30px auto;padding:0 24px}}
h1{{font-size:30px}}aside{{padding:20px;background:#17222d;border-left:3px solid #e8b767}}
section{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px}}
figure{{margin:0}}img{{width:100%;height:auto}}figcaption{{padding:10px 0;color:#bacbd7}}</style>
<h1>MEWA ARENA · Erste isolierte Modellprüfung</h1>
<p>Original-Unity-Modell, unveränderte Geometrie, vereinfachte Browsermaterialien.
Lokale Wirtschaftskapazität: {review['capacityFromDatabase']} Plätze.
{review['sourceSeatCount']} Quellsitze sind kein neuer Kapazitätswert.</p>
<aside><strong>Noch keine Freigabe oder Registrierung.</strong>
Das geografische Umfeld ist wegen Konflikten zwischen alten OSM-Flächen und
der quellbasierten Geländeaussparung nicht geladen. Keine Quellflächen wurden gelöscht.
Die 3D-Bilder zeigen ausschließlich das Originalmodell mit seinem Quellboden.
Orientierungsabnahme, Umfeld und Einbau in die aktuellen Editoren bleiben offen.
Die 2D-Abbildung ist nur die vorhandene Quellblaupause.</aside>
<p>Spielfeld geprüft: 105 × 68 m. Dach: {review['roofMeshCount']} getrennte Quellmeshes.
Zwölf Browserlichtquellen aus {manifest['verifiedFixtureCount']} geprüften Unity-Komponenten.
Keine vollständige Nachbildung der Unity-Shader oder gebackenen Beleuchtung.</p>
<section>{''.join(panels)}</section></html>"""
    (OUT / "mainz-modellpruefung.html").write_text(report)
    print("Packaged six clearly labelled review views; isolated source model only.")


if __name__ == "__main__":
    main()
