"""Build the explicitly conditional height/sight report, never a background asset."""
import base64
import hashlib
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from geo_probe_geometry import polygon_mask

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated-artifacts/elversberg-height-visibility"
BASE = ROOT / "generated-artifacts/stadium-main-stand-back-probe"
LANDMARKS = (30887518, 53864244)


def read_ids(name):
    rgba = np.fromfile(OUT / f"{name}.rgba", dtype=np.uint8).reshape(940, 1880, 4)[::-1]
    rgb = rgba[:, :, :3].astype(np.uint32)
    return rgb[:, :, 0] + 256 * rgb[:, :, 1] + 65536 * rgb[:, :, 2]


def counts(ids, index, keep):
    return {"roof_pixels": int(np.sum((ids == 2 * index + 1) & ~keep)),
            "facade_pixels": int(np.sum((ids == 2 * index + 2) & ~keep)),
            "raw_field_overlap_pixels": int(np.sum(
                ((ids == 2 * index + 1) | (ids == 2 * index + 2)) & keep))}


def embed(path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def main():
    inputs = json.loads((OUT / "height_inputs.json").read_text())
    render = json.loads((OUT / "render_verification.json").read_text())
    geo = json.loads((BASE / "geo_verification.json").read_text())
    assert render["camera"] == inputs["camera"]
    camera = inputs["camera"]
    keep = polygon_mask(camera, [(-52.5, -34), (52.5, -34), (52.5, 34), (-52.5, 34)])
    assert int(keep.sum()) == 416792
    objects = {o["osm_id"]: o for o in inputs["objects"]}
    results = {}
    for roof in ("roof", "no_roof"):
        ids = read_ids(f"all_{roof}")
        # Instance colors also tint the stadium-only material. Occupancy is
        # any nonblack pixel, not only the pure yellow material code.
        stadium = read_ids(f"stadium_{roof}") != 0
        silhouette = np.asarray(Image.open(BASE / f"elversberg_{roof}_silhouette.png").convert("L")) > 128
        mismatch = int(np.sum(stadium != silhouette))
        assert mismatch / stadium.size < .0015, "Fresh stadium occupancy parity failed"
        rows = []
        for osm_id in LANDMARKS:
            index = render["objects"].index(osm_id)
            o = objects[osm_id]
            alone = counts(read_ids(f"{osm_id}_alone_{roof}"), index, keep)
            with_stadium = counts(read_ids(f"{osm_id}_stadium_{roof}"), index, keep)
            all_buildings = counts(ids, index, keep)
            for kind in ("roof_pixels", "facade_pixels"):
                assert 0 <= all_buildings[kind] <= with_stadium[kind] <= alone[kind]
            rows.append({
                "osm_id": osm_id, "name": o["name"],
                "envelope_height_m": o["height_envelope_m"],
                "alone": alone, "with_stadium": with_stadium,
                "with_measured_neighbours": all_buildings,
                "stadium_occluded_pixels": sum(alone[k] - with_stadium[k]
                                               for k in ("roof_pixels", "facade_pixels")),
                "neighbour_occluded_pixels": sum(with_stadium[k] - all_buildings[k]
                                                for k in ("roof_pixels", "facade_pixels")),
                "original_ground_visible_pixels": next(
                    f["visible_ground_pixels"] for f in
                    geo["elversberg"]["states"][f"elversberg_{roof}"]["mapped_visible_features"]
                    if f["osm_id"] == osm_id),
                "classification": "Conditional geometric envelope only; not proven original facade",
            })
        sweep = {str(h): counts(read_ids(f"lidl_h{h}_{roof}"), len(render["objects"]), keep)
                 for h in (3, 6, 9, 12)}
        original = np.asarray(Image.open(BASE / f"elversberg_{roof}.png").convert("RGB"))
        diagnostic = original.copy()
        # Other measured neighbourhood envelopes: purple, deliberately not
        # photorealistic. Target roof/wall colors differ visibly.
        measured = (ids > 0) & (ids <= 2 * len(render["objects"])) & ~keep
        diagnostic[measured] = (145, 129, 160)
        palette = {30887518: ((38, 178, 161), (17, 105, 102)),
                   53864244: ((251, 171, 64), (166, 87, 30))}
        for osm_id in LANDMARKS:
            index = render["objects"].index(osm_id)
            cap, wall = palette[osm_id]
            diagnostic[(ids == 2 * index + 1) & ~keep] = cap
            diagnostic[(ids == 2 * index + 2) & ~keep] = wall
        assert np.array_equal(diagnostic[keep], original[keep]), "Field pixels changed"
        Image.fromarray(diagnostic).save(OUT / f"height_envelopes_{roof}.png")
        # The corresponding sensitivity picture has a conspicuously magenta
        # Lidl envelope and is labeled as an assumed, not measured, height.
        lidl_ids = read_ids(f"lidl_h6_{roof}")
        sensitivity = diagnostic.copy()
        n = len(render["objects"])
        sensitivity[((lidl_ids == 2*n+1) | (lidl_ids == 2*n+2)) & ~keep] = (223, 54, 171)
        assert np.array_equal(sensitivity[keep], original[keep])
        Image.fromarray(sensitivity).save(OUT / f"lidl_assumed_6m_{roof}.png")
        results[roof] = {
            "landmarks": rows, "lidl_assumed_height_sweep_m": sweep,
            "stadium_occupancy_pixel_mismatch": mismatch,
            "mismatch_reason": "Non-MSAA ID occupancy vs thresholded antialiased white silhouette",
            "protected_pitch_pixels": int(keep.sum()), "pitch_pixels_identical": True,
        }
    report = {
        "classification": inputs["classification"],
        "decision": "Wasgau and TVE height envelopes have conditional roof AND wall visibility. "
                    "Lidl height unresolved. No verified complete facade/tree background release.",
        "states": results, "matching": inputs["matching"], "provenance": inputs["provenance"],
        "limits": inputs["limits"], "camera_matrices_unchanged": True,
        "field_pixels_unchanged": True, "source_locations_unchanged": True,
    }
    report["source_sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (OUT / "height_inputs.json", OUT / "render_verification.json",
         OUT / "sources/sportstaettenkonzept.pdf", OUT / "sources/tve-original-page.png")
    }
    (OUT / "height_visibility.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    table = []
    md_rows = []
    for roof, state in results.items():
        for row in state["landmarks"]:
            a, s, n = [row[key] for key in ("alone", "with_stadium", "with_measured_neighbours")]
            cols = [row["name"], "an" if roof == "roof" else "aus",
                    f'{row["envelope_height_m"]:.3f}',
                    str(row["original_ground_visible_pixels"]),
                    str(a["roof_pixels"]), str(a["facade_pixels"]),
                    str(s["facade_pixels"]), str(n["roof_pixels"]), str(n["facade_pixels"])]
            table.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cols) + "</tr>")
            md_rows.append("| " + " | ".join(cols) + " |")
    headers = ["Objekt", "Stadiondach", "Hüllhöhe m", "Boden alt px", "Dach allein px",
               "Wand allein px", "Wand + Stadion px", "Dach + Umfeld px", "Wand + Umfeld px"]
    heading = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
    conclusion = """<h1>Elversberg: Höhen- und Sichtprüfung</h1>
<p><strong>Bedingte Geometrieprüfung — keine verifizierte Fotokulisse.</strong> Stand der Recherche: 10.10.2026.
Die bestätigte Nordostkamera, das 1880×940-Format, die Feldprojektion und alle OSM-Standorte bleiben unverändert.</p>
<h2>Was die Quellen belegen</h2>
<ul><li><strong>Wasgau, OSM 30887518:</strong> amtliche Gebäudekomponenten mit 9,314 m und 9,379 m.
Grundrissüberlappung des Hauptkörpers: 73,24 % IoU; Version im Dienst: 05.03.2024.</li>
<li><strong>TVE-Halle, OSM 53864244:</strong> amtliche Komponenten mit 14,204 m und 11,002 m.
Hauptkörper: 73,41 % IoU; Version 05.03.2024. Ein Originalfoto im kommunalen Sportstättenkonzept
von 2017 zeigt eine aufrechte Backsteinfassade mit geneigtem Dach, aber keine vermessene Höhe.</li>
<li><strong>Lidl, OSM 53864241:</strong> keine belastbare Höhenzuordnung. Der beste amtliche
Grundriss trifft nur 3,33 % IoU. Seine 6,105 m werden ausdrücklich <em>nicht</em> als Lidl-Höhe verwendet.
Die offizielle Filialseite bestätigt Lindenstr. 3b, enthält aber kein geeignetes Gebäudefoto.
Die Bildsuche lieferte Prospekte statt Standortfotos. Eine weitere BuildingPart-Abfrage scheiterte
am amtlichen Dienst; die Fehlerantwort bleibt im Quellenpaket.</li></ul>
<h2>Wie geprüft wurde</h2>
<p>Die amtlichen Werte sind als „measured“ ausgewiesen; untere Höhenreferenz unbekannt, obere Referenz nicht befüllt.
Hier werden die unveränderten OSM-Grundrisse auf y=0 zu bewusst vereinfachten Blockhüllen
bis zur größten zugeordneten Komponenten-Höhe extrudiert. Das ist weder das echte LoD2-Dach noch eine
Fassadenrekonstruktion. Bei TVE überschätzt die 14,204-m-Hülle insbesondere den niedrigeren Gebäudeteil.</p>
<p>Ein echter WebGL-Tiefenpuffer trennt Dach und Wände. Gezählt wird jeweils das Objekt allein,
mit dem bestehenden Stadion samt korrektem Dachzustand und mit allen zugeordneten Gebäudehüllen.
158 Nachbargrundrisse konnten im Quellenfenster zugeordnet werden; von 70 ursprünglich bodensichtbaren
Gebäuden sind 43 zugeordnet und 27 bleiben höhenmäßig offen. Der Schnittwert 45 % IoU ist eine
offengelegte Zuordnungsregel, keine amtliche Identitätsgarantie. Nicht zugeordnete Gebäude werden nicht
mit geratenen Höhen eingesetzt. Pixelzahlen sind rasterabhängige Diagnosewerte, keine vermessenen Quadratmeter.</p>
<p>Die 416.792 Feldpixel werden in jeder Vergleichsabbildung exakt aus dem Originalrender erhalten.
Gezählte Objektpixel liegen außerhalb der Feldmaske; mögliche rohe Feldüberlagerungen stehen separat im JSON.
Die produktive Szene und Datenbank wurden nicht verändert.</p>"""
    sections = ""
    for roof in ("roof", "no_roof"):
        label = "Dach an" if roof == "roof" else "Dach aus"
        sections += f"""<h2>{label}: gemessene Höhen als vereinfachte Hüllen</h2>
<p>Wasgau: türkis, TVE: orange; helle Flächen = Hülldach, dunkle = Wand.
Andere zugeordnete Gebäude: violett. Unmodellierte Bodenflächen bleiben aus dem Originalrender sichtbar.
Das Bild ist eine Diagnose, keine neue Hintergrundvorlage.</p>
<img alt="Bedingte Gebäudehüllen, {label}" src="{embed(OUT / f'height_envelopes_{roof}.png')}">
<details><summary>Lidl: ausschließlich Sensitivität bei angenommenen 6 m anzeigen</summary>
<p>Magenta ist eine freie Testannahme, keine belegte Gebäudehöhe.</p>
<img alt="Nicht belegte Lidl-Hüllhöhe 6 m" src="{embed(OUT / f'lidl_assumed_6m_{roof}.png')}"></details>"""
    sweep_rows = []
    for roof, state in results.items():
        for height, count in state["lidl_assumed_height_sweep_m"].items():
            sweep_rows.append(f'<tr><td>{"an" if roof == "roof" else "aus"}</td><td>{height}</td>'
                              f'<td>{count["roof_pixels"]}</td><td>{count["facade_pixels"]}</td></tr>')
    limits = """<h2>Einordnung und Entscheidung</h2>
<p><strong>Wasgau und TVE sind in dieser festen Kamera nicht bloß als Bodenflächen getroffen:
Auch aufrechte Hüllwände bleiben unter den geprüften Höhen sichtbar.</strong> Die gemessenen Nachbarhüllen
reduzieren die Sicht; deshalb genügt die frühere Bodenkarte nicht als Vorlage.
Das ist ein bedingter geometrischer Nachweis, kein Nachweis der vollständigen Originalfassaden.</p>
<p>Für Lidl ist nur eine ausdrücklich angenommene 3/6/9/12-m-Sensitivität vorhanden.
Eine belegte Höhe oder ein geeignetes aktuelles Standortfoto fehlt. Keine dieser Testhöhen darf
in einer neuen Kulisse als Tatsache erscheinen.</p>
<p>Geländehöhen relativ zum Spielfeld, echte Dachformen, die 27 ungeklärten bodensichtbaren Gebäude
und Baumkronen sind nicht vollständig erfasst. OSM-Waldflächen beweisen weder Baumhöhe noch Kronendichte.
Es gibt daher <strong>keine Freigabe für eine ortsverifizierte Hintergrundvorlage</strong>.
Vor einer solchen Vorlage sind Lidl-Identität/Höhe sowie Gelände- und Vegetationsverdeckung zu klären.
Kamera und Landmarken dürfen hierfür nicht verschoben werden. Keine KI-Erstellung, kein produktiver Einbau.</p>
<h2>Originalfotobeleg: TVE-Halle</h2>
<p>Gemeinde Spiesen-Elversberg, Sportstättenkonzept vom 15.12.2017, PDF-Seite 24:
historischer Form-/Materialbeleg; Aufnahmedatum unbekannt, kein Beleg des heutigen Bauzustands oder dieser Kamera.</p>"""
    links = [
        ("Amtlicher LoD2-Dienst", "https://geoportal.saarland.de/spatial-objects/407"),
        ("Kommunales Sportstättenkonzept, Seite 24", "https://www.spiesen-elversberg.de/fileadmin/user_upload/Spiesen-Elversberg/PDF/Sportstaettenkonzept.pdf#page=24"),
        ("Offizielle Lidl-Filiale", "https://www.lidl.de/s/de-DE/filialen/spiesen-elversberg/lindenstr-3b/"),
        ("Wasgau-Grundriss", "https://www.openstreetmap.org/way/30887518"),
        ("Lidl-Grundriss", "https://www.openstreetmap.org/way/53864241"),
        ("TVE-Grundriss", "https://www.openstreetmap.org/way/53864244"),
    ]
    sources = "<h2>Quellen und Reproduktion</h2><ul>" + "".join(
        f'<li><a href="{url}">{title}</a></li>' for title, url in links) + "</ul>"
    sources += """<p>©LVGL 2022, dl-de/by-2-0, www.lvgl.saarland.de.
OSM: © OpenStreetMap contributors, ODbL 1.0. Amtliche Versionsdaten sind keine Luftbild-Aufnahmedaten.
Quellantworten, Abfrageparameter, SHA-256, Einzelpässe und Feld-/Kameraprüfungen im Begleitpaket.</p>
<pre>python scripts/prepare_elversberg_height_probe.py
node scripts/export_elversberg_height_probe.mjs
python scripts/build_elversberg_height_report.py
python scripts/test_elversberg_height_probe.py</pre>"""
    content = conclusion + '<div class="table"><table>' + heading + "".join(table) + "</table></div>" + sections
    content += '<h2>Lidl: unbewiesene Höhen, nur Sensitivität</h2><table><tr><th>Stadiondach</th><th>Annahme m</th><th>Dach px</th><th>Wand px</th></tr>' + "".join(sweep_rows) + "</table>"
    content += limits + f'<img class="photo" alt="Historische kommunale Originalfotoseite" src="{embed(OUT / "sources/tve-original-page.png")}">' + sources
    document = """<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Elversberg Höhen-/Sichtprüfung</title>
<style>body{font:16px/1.55 system-ui,sans-serif;color:#202b33;background:#f6f7f8;max-width:1200px;margin:32px auto;padding:0 20px}
h1{font-size:30px}h2{margin-top:36px}img{width:100%;height:auto;background:#18252b}img.photo{max-width:560px}
table{border-collapse:collapse;background:white;width:100%;font-size:14px}td,th{padding:9px;border:1px solid #c8d1d8;text-align:left}
.table{overflow:auto}summary{cursor:pointer;font-weight:bold;padding:15px 0}pre{overflow:auto;background:white;padding:16px}</style>""" + content + "</html>"
    (OUT / "report.html").write_text(document)
    md = "# Elversberg: bedingte Höhen- und Sichtprüfung\n\n"
    md += report["decision"] + "\n\n"
    md += "| " + " | ".join(headers) + " |\n|" + "---|" * len(headers) + "\n" + "\n".join(md_rows)
    md += "\n\n## Quellen, Methodik und Einschränkungen\n\n"
    md += "\n".join(f"- {limit}" for limit in inputs["limits"])
    md += "\n\nDer vollständige deutschsprachige Bericht mit Quellen und Abbildungen ist `report.html`.\n"
    (OUT / "README.md").write_text(md)
    board = Image.new("RGB", (1880, 1030), "#f6f7f8")
    draw = ImageDraw.Draw(board)
    draw.text((20, 12), "ELVERSBERG: BEDINGTE HOEHENHUELLEN, KEINE FOTOKULISSE | KAMERA UND FELD UNVERAENDERT", fill="#202b33")
    for i, roof in enumerate(("roof", "no_roof")):
        board.paste(Image.open(OUT / f"height_envelopes_{roof}.png").resize((940, 470)), (940*i, 55))
        draw.text((940*i+20, 540), f"Dach {'an' if roof == 'roof' else 'aus'} | Wasgau: tuerkis | TVE: orange", fill="#202b33")
    draw.text((20, 585), "Gemessene Komponenten: Wasgau 9.314/9.379 m; TVE 11.002/14.204 m. Lidl: Hoehe UNBEKANNT.", fill="#202b33")
    draw.text((20, 620), "Flaches Bezugsniveau; vereinfachte Blockhuellen; keine echten Dachformen; Baeume und unbekannte Gebaeude fehlen.", fill="#202b33")
    board.crop((0, 0, 1880, 680)).save(OUT / "comparison.jpg", quality=92)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
