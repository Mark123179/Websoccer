"""Verify and present the fresh Mainz surroundings, without changing the app."""
import base64
import hashlib
import html
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from scripts.package_mainz_review import font

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "generated-artifacts/mainz-study"
OUT = STUDY / "osm-fresh"


def read(name):
    return json.loads((OUT / name).read_text())


def main():
    evidence, manifest = read("evidence.json"), read("manifest.json")
    presentation = read("presentation.json")["presentation"]
    data, terrain, renders = presentation["surroundings"], read("terrain-check.json"), read("render-evidence.json")
    assert terrain["ok"] and terrain["terrainDeclared"] and not terrain["findings"]
    assert evidence["rawSha256"] == hashlib.sha256((OUT / "raw.json").read_bytes()).hexdigest()
    assert manifest["geometrySha256"] == hashlib.sha256(
        (STUDY / "source-export/geometry.bin").read_bytes()).hexdigest()
    assert manifest["clubFmiId"] == presentation["clubFmiId"] == 918
    assert len(renders) == 4
    for row in renders:
        assert row["assetVersion"] == manifest["assetVersion"] and not row["errors"]
        assert row["evidence"]["counts"] == evidence["counts"]
        assert row["evidence"]["terrain"]["omitted"] == {"green": [], "water": []}
        assert abs(row["evidence"]["environmentY"] - data["groundLevel"]) < 1e-8
    assert len(data["buildings"]) == len(data["buildingHeights"]) == len(data["buildingIds"])
    for road, source in zip(data["roads"], evidence["features"]["roads"]):
        assert abs(road["w"] * 2.5 - source["displayWidthMeters"]) < 1e-8
    unique = {kind: len({row["osm"] for row in rows})
              for kind, rows in evidence["features"].items()}

    # True-north-up source plan. A viewport crop, not a mutation of OSM geometry.
    image = Image.new("RGB", (1200, 900), "#061018")
    draw = ImageDraw.Draw(image)
    def project(p):
        return (600 + p[0] * .98, 465 - p[1] * .98)
    for kind, fill, outline in [
        ("green", "#0b302b", "#176f60"), ("water", "#06374b", "#24aacc"),
        ("buildings", "#123241", "#2594a5"),
    ]:
        for polygon in data[kind]:
            draw.polygon([project(p) for p in polygon], fill=fill, outline=outline)
    for road in data["roads"]:
        draw.line([project(p) for p in road["p"]], fill="#245965",
                  width=max(1, round(road["w"] * 2.5 * .98)))
    for point in data["trees"]:
        x, y = project(point)
        draw.ellipse((x-2,y-2,x+2,y+2),fill="#38c68b")
    theta = presentation["frame"]["axisTheta"]
    def inverse(p):
        x, z = p
        return [z * math.cos(theta) + x * math.sin(theta),
                z * math.sin(theta) - x * math.cos(theta)]
    outline = evidence["mappedStadiumModelCoordinates"]
    draw.polygon([project(inverse(p)) for p in outline], fill="#682c3e", outline="#d295a2")
    pitch = [inverse(p) for p in [(-34,-52.5),(34,-52.5),(34,52.5),(-34,52.5)]]
    draw.polygon([project(p) for p in pitch],fill="#295d3b",outline="white",width=2)
    draw.line([project(inverse((-34,0))),project(inverse((34,0)))],fill="white",width=2)
    draw.rectangle((0,0,1200,97),fill="#061018")
    draw.text((24,17),"MAINZ · NEUER OSM-AUSZUG",font=font(28),fill="white")
    draw.text((24,58),"Nord oben · reales Spielfeld als Bezug · kein neuer Kapazitäts- oder Stadionentwurf",
              font=font(17),fill="#b8cdd6")
    draw.polygon([(1151,126),(1142,150),(1160,150)],fill="#b9e6f0")
    draw.text((1144,157),"N",font=font(20),fill="white")
    draw.rectangle((0,854,1200,900),fill="#061018")
    draw.text((24,865),"© OpenStreetMap contributors · ODbL · Ausschnitt der 1.600 × 1.600-m-Auswahl",
              font=font(17),fill="#b8cdd6")
    image.save(OUT / "ansichten/2d-osm-plan.png")
    views = [
        ("2d-osm-plan", "Neue OSM-Umgebung · Nord oben"),
        ("3d-editor-dach-an", "Originalmodell und neues Umfeld · Tag"),
        ("draufsicht", "3D-Draufsicht · Straßen und kartierte Bäume"),
        ("ticker-tag-dach-an", "Gemeinsame Spielkamera · Tag"),
        ("ticker-nacht-flutlicht", "Gemeinsame Spielkamera · Nacht und Flutlicht"),
    ]
    sheet = Image.new("RGB", (1440, 1465), "#071018")
    d = ImageDraw.Draw(sheet)
    d.text((24,16),"MAINZ · ORIGINALSTADION MIT NEUEM OSM-UMFELD",font=font(28),fill="white")
    d.text((24,58),"Geländeprüfung: ohne Konflikte · Vorschau, noch nicht registriert",
           font=font(19),fill="#66dcb2")
    panels = []
    for i, (name, title) in enumerate(views):
        path = OUT / "ansichten" / f"{name}.png"
        original = Image.open(path).convert("RGB")
        original.thumbnail((700,394),Image.Resampling.LANCZOS)
        panel = Image.new("RGB",(700,394),"#071018")
        panel.paste(original,((700-original.width)//2,(394-original.height)//2))
        x, y = 13+(i%2)*714, 100+(i//2)*439
        sheet.paste(panel,(x,y))
        d.text((x+5,y+401),title,font=font(18),fill="#d3e2ec")
        encoded = base64.b64encode(path.read_bytes()).decode()
        panels.append(f'<figure><img src="data:image/png;base64,{encoded}" alt="{html.escape(title)}">'
                      f'<figcaption>{html.escape(title)}</figcaption></figure>')
    x, y = 748, 100+2*439
    for i, line in enumerate([
        "Geprüfter Stand",
        f"{unique['buildings']} Gebäudeobjekte · {unique['trees']} kartierte Bäume",
        f"{unique['roads']} Straßen-/Wegeobjekte",
        "Keine OSM-Fläche am Stadion zugeschnitten",
        "Keine Grün-/Wasserfläche vom Renderer ausgelassen",
        "Höhen überwiegend schematisch; Gelände eben",
        "Kapazität: unverändert 33.305 Plätze",
        "Keine Registrierung oder Datenbankänderung",
    ]):
        d.text((x,y+32+i*38),line,font=font(19 if i else 24),fill="#d3e2ec")
    sheet.save(OUT / "mainz-neues-osm-umfeld.jpg",quality=91)
    body = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mainz · Neues OSM-Umfeld</title>
<style>body{{font:16px system-ui;background:#071018;color:#dce9f1;max-width:1500px;margin:28px auto;padding:0 24px}}
aside{{padding:18px;border-left:3px solid #65d4af;background:#11232a}}
section{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:24px}}
figure{{margin:0}}img{{width:100%}}figcaption{{padding:10px 0;color:#bbd0dc}}a{{color:#69d4ed}}</style>
<h1>Mainz · Neues OSM-Umfeld am Originalstadion</h1>
<p>Frischer Auszug aus der OSM-API, Abruf: {html.escape(evidence['fetch']['fetchedAt'])}.
Spielfeldbezug: <a href="https://www.openstreetmap.org/way/{evidence['pitchWay']}">OSM-Weg {evidence['pitchWay']}</a>.
{unique['buildings']} unterschiedliche Gebäudeobjekte, {unique['roads']} Straßen-/Wegeobjekte
und {unique['trees']} kartierte Einzelbäume in der Auswahl.</p>
<aside><strong>Vorschau, noch nicht registriert.</strong> Geometrie und Kapazität des Originalstadions
bleiben unverändert. Geländeprüfung und vier echte Browserrenderings ohne Konflikte oder Seitenfehler.
Keine OSM-Flächen am Stadion zugeschnitten; der Renderer lässt keine Grün-/Wasserflächen aus.
Das Stadion selbst wird nur durch Unity dargestellt, nicht zusätzlich als OSM-Bauklotz.</aside>
<p>Grenzen: ebenes Gelände auf Höhe des Quellumlaufs, keine amtliche Höhenvermessung.
Gebäudehöhen aus vorhandenen OSM-Höhen oder Geschosszahlen, sonst schematisch;
Baumkronen und Straßenbreiten ohne Messangabe sind schematisch.
Drei im API-Ausschnitt unvollständige Multipolygon-Grenzen bleiben als Datenlücken dokumentiert;
unterirdische Wege werden nicht als oberirdische Wege gezeichnet.
Das OSM-Spielfeldpolygon beschreibt einschließlich Auslauf ungefähr 118 × 77 m.
Die Originalmarkierungen bleiben 105 × 68 m; das Modell wurde nicht skaliert.</p>
<section>{''.join(panels)}</section>
<p>© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>,
ODbL. Die 2D-Abbildung ist ein Quellplan, kein bereits eingebauter Live-Editor.</p></html>"""
    (OUT / "mainz-osm-pruefung.html").write_text(body)
    checks = {"terrain": terrain, "distinctSourceObjects": unique,
              "renderedGeometryCounts": evidence["counts"], "browserCaptures": len(renders),
              "geometrySha256": manifest["geometrySha256"], "sourceDataUnchanged": True,
              "rendererOmissions": {"green": [], "water": []},
              "roadWidthsUseRendererUnits": True, "registered": False, "databaseWrites": False}
    (OUT / "checks.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2))
    print(json.dumps(checks,ensure_ascii=False))


if __name__ == "__main__":
    main()
