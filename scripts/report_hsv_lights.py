"""Verify the HSV lighting captures and produce a self-contained review report."""
import argparse
import base64
from collections import Counter
import csv
import hashlib
import html
from io import BytesIO
import json
import math
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image, ImageDraw

from scripts.stadium_light_surfaces import rejection_reasons
from stadium_editor.model_registry import validate_model_manifest

STATES = ("day-off", "day-on", "night-off", "night-on")
LABELS = ("Tag · Flutlicht aus", "Tag · Flutlicht an",
          "Nacht · Flutlicht aus", "Nacht · Flutlicht an")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(study):
    candidate_raw = (study / "manifest.json").read_bytes()
    baseline_raw = (study / "baseline-manifest.json").read_bytes()
    candidate, baseline = json.loads(candidate_raw), json.loads(baseline_raw)
    validate_model_manifest(candidate)
    validate_model_manifest(baseline)
    package = study / "package"
    if json.loads((package / "models/947.json").read_text()) != candidate:
        raise ValueError("Packaged manifest differs")
    for name, expected in candidate["assetSha256"].items():
        if sha((package / "stadium-models/947" / candidate["assetVersion"] / name).read_bytes()) != expected:
            raise ValueError(f"Packaged asset differs: {name}")
    audit = json.loads((study / "light-audit.json").read_text())
    rows = audit["candidates"]
    records = json.loads((study / "views/render-evidence.json").read_text())
    expected_names = {f"{variant}-{state}" for variant in ("baseline", "candidate") for state in STATES}
    if {r["name"] for r in records} != expected_names or len(records) != 8:
        raise ValueError("Exactly eight baseline/candidate lighting states are required")
    allowed = {"fixtures", "verifiedFixtureCount", "assetVersion", "lightingRevision"}
    if {k: v for k, v in candidate.items() if k not in allowed} != {
            k: v for k, v in baseline.items() if k not in allowed}:
        raise ValueError("Non-lighting manifest data changed")
    if candidate["assetVersion"] == baseline["assetVersion"]:
        raise ValueError("Lighting revision must have its own version")
    row_by_id = {r["id"]: r for r in rows}
    accepted = {r["id"] for r in rows if not r["surfaceRejections"]}
    represented = [id for f in candidate["fixtures"] for id in f["representedIds"]]
    if len(represented) != len(set(represented)) or set(represented) != accepted:
        raise ValueError("Source-light partition is not complete and disjoint")
    if candidate["verifiedFixtureCount"] != len(accepted):
        raise ValueError("Verified source count differs")
    if any(n > 3 for n in Counter(f["stand"] for f in candidate["fixtures"]).values()):
        raise ValueError("More than three sources on one stand")
    for fixture in candidate["fixtures"]:
        original = row_by_id[fixture["id"]]
        for field in ("position", "direction", "angle", "range", "color", "sourceIntensity"):
            if fixture[field] != original[field]:
                raise ValueError(f"Source value changed: {fixture['id']} {field}")
        if fixture["intensity"] != fixture["sourceIntensity"]*fixture["browserIntensityScale"]:
            raise ValueError("Browser intensity was not derived from original source")
    for row in rows:
        for mode, distance_key in (("surface", "meshDistance"), ("vertex", "vertexDistance")):
            if row[mode+"Rejections"] != rejection_reasons(
                    row["position"], row["direction"], row[distance_key]):
                raise ValueError("Candidate rejection evidence differs")
    camera = records[0]["evidence"]["camera"]
    images = {}
    for record in records:
        variant, state = record["name"].split("-", 1)
        raw = candidate_raw if variant == "candidate" else baseline_raw
        manifest = candidate if variant == "candidate" else baseline
        evidence = record["evidence"]
        if record["manifestSha256"] != sha(raw) or record["errors"]:
            raise ValueError("Render is not bound to the reviewed manifest")
        if evidence["camera"] != camera or evidence["exposure"] != 1.2 or not evidence["roofVisible"]:
            raise ValueError("Camera, exposure or roof changed")
        if evidence["day"] != state.startswith("day-") or evidence["floodlight"] != state.endswith("-on"):
            raise ValueError("Day/floodlight states are coupled or mislabeled")
        if evidence["scale"] != 1:
            raise ValueError("A calibration trial is not a final-package capture")
        if len(evidence["lights"]) != len(manifest["fixtures"]) or len(evidence["lights"]) > 12:
            raise ValueError("Functional source count differs")
        for light, fixture in zip(evidence["lights"], manifest["fixtures"]):
            intensity = fixture["intensity"]*8*min(4, math.sqrt(len(fixture["representedIds"])))
            target = np.asarray(fixture["position"])+50*np.asarray(fixture["direction"])
            if (light["id"] != fixture["id"] or light["position"] != fixture["position"] or
                    not np.allclose(light["target"], target, rtol=0, atol=1e-9) or
                    not math.isclose(light["angle"], math.radians(fixture["angle"]/2)) or
                    light["distance"] != fixture["range"] or
                    not math.isclose(light["onIntensity"], intensity) or
                    not math.isclose(light["intensity"], intensity if evidence["floodlight"] else 0)):
                raise ValueError("Rendered source differs from original-light declaration")
        image = (study / "views" / (record["name"]+".png")).read_bytes()
        if sha(image) != record["imageSha256"]:
            raise ValueError("Capture hash differs")
        images[record["name"]] = image
    for state in ("day-off", "night-off"):
        if images["baseline-"+state] != images["candidate-"+state]:
            raise ValueError("Floodlight-off appearance changed")
    measurements = {}
    for name, image in images.items():
        pixels = np.asarray(Image.open(BytesIO(image)).convert("RGB"))
        luma = pixels @ np.array([.2126, .7152, .0722])
        measurements[name] = {
            # Fixed screen-space interior sample, NOT lux or pitch-uniformity.
            "sampleBoundsXYXY": [320, 380, 900, 600],
            "sampleMeanSRGBLuma": float(luma[380:600, 320:900].mean()),
            "nearWhiteRGB250Fraction": float(np.all(pixels >= 250, axis=2).mean()),
        }
    return audit, baseline, candidate, images, measurements


def report(study):
    audit, baseline, candidate, images, measurements = verify(study)
    summary = audit["summary"]
    registry = Path(__file__).resolve().parents[1] / "stadium_editor/blueprints/v2/models/947.json"
    if sha(registry.read_bytes()) != summary["baselineManifestSha256"]:
        raise ValueError("The approved HSV registry changed during the study")
    ratio = (measurements["candidate-night-on"]["sampleMeanSRGBLuma"] /
             measurements["baseline-night-on"]["sampleMeanSRGBLuma"])
    def embedded(image):
        return "data:image/png;base64," + base64.b64encode(image).decode()
    pairs = []
    sheet = Image.new("RGB", (1200, 4*368+45), "#0c151b")
    draw = ImageDraw.Draw(sheet)
    draw.text((15, 12), "HSV - identische Kamera / links bisher / rechts Kandidat", fill="white")
    for index, (state, label) in enumerate(zip(STATES, LABELS)):
        left, right = images["baseline-"+state], images["candidate-"+state]
        pairs.append(f'<h3>{html.escape(label)}</h3><div class="pair">'
                     f'<figure><img alt="Bisher: {html.escape(label)}" src="{embedded(left)}"><figcaption>Bisher</figcaption></figure>'
                     f'<figure><img alt="Kandidat: {html.escape(label)}" src="{embedded(right)}"><figcaption>Kandidat</figcaption></figure></div>')
        top = 45+index*368
        draw.text((15, top+8), label, fill="white")
        for col, image in enumerate((left, right)):
            thumb = Image.open(BytesIO(image)).convert("RGB").resize((600, 338))
            sheet.paste(thumb, (col*600, top+28))
    sheet.save(study / "vergleich.jpg", quality=88)
    distances = np.array([[r["vertexDistance"], r["meshDistance"]] for r in audit["candidates"]])
    source_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in (
            f["id"], ", ".join(f"{p:.3f}" for p in f["position"]),
            f'{f["meshDistance"]:.3f}', f["sourceIntensity"], f["intensity"],
            len(f["representedIds"]))) + "</tr>" for f in candidate["fixtures"])
    document = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>HSV · geprüfte Nachtkalibrierung</title>
<style>body{{margin:0 auto;padding:32px;max-width:1350px;background:#0c151b;color:#e7eef2;font:16px/1.55 system-ui}}
h1,h2,h3{{line-height:1.2}}h2{{margin-top:40px}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
figure{{margin:0}}img{{width:100%;height:auto}}figcaption{{color:#a7bbc9}}code{{overflow-wrap:anywhere}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #34434d}}
.notice{{padding:16px;border-left:3px solid #ffcc74;background:#18212a}}@media(max-width:700px){{body{{padding:16px}}.pair{{grid-template-columns:1fr}}table{{display:block;overflow:auto}}}}</style>
<h1>HSV · geprüfte Nachtkalibrierung</h1>
<p class="notice">Separates Prüfpaket, noch nicht aktiviert. Das registrierte Paket
<code>{baseline['assetVersion']}</code> und die bestehende HSV-Integration bleiben unverändert.
Kandidat: <code>{candidate['assetVersion']}</code>. Kein automatisches Überschreiben.</p>
<h2>Ergebnis der Quellenprüfung</h2>
<ul><li>{summary['enabledSpotlights']} aktive Unity-Spotlight-Komponenten geprüft; {summary['surfaceAccepted']} bestanden weiterhin.
Der Wechsel vom Vertex- zum exakten Dreiecksflächenabstand erschließt <strong>keine zusätzliche Quelle</strong>.</li>
<li>397 Komponenten liegen mehr als 2 m vom geprüften Lampenmesh entfernt. Davon verfehlen 104 zusätzlich mit ihrer Achse den bisherigen Spielfeld-Prüfbereich (±40 × ±60 m).
Die 104 sind in den 397 enthalten, nicht zusätzlich.</li>
<li>Der größte Abstandsunterschied zwischen beiden Messmethoden beträgt {float((distances[:, 0]-distances[:, 1]).max()):.6f} m.
Die knappste abgewiesene Quelle liegt {min(r['meshDistance'] for r in audit['candidates'] if r['surfaceRejections']):.3f} m entfernt.</li>
<li>Lampenbeleg: Quellmesh <code>{candidate['fixtures'][0]['nearestLampMesh']['meshPathId']}</code>, Material 56,
Textur <code>tex_bm_56</code>, 360 originale Dreiecke. Keine Dachmembranen oder Werbeflächen als Lampen umgedeutet.</li></ul>
<h2>Kalibrierung ohne erfundene Lichtpunkte</h2>
<p>Drei reale Quellpositionen auf WEST repräsentieren die 19 zulässigen Komponenten
(statt neun teilweise nahezu deckungsgleicher Repräsentanten).
Keine aus Mittelwerten erzeugten Positionen; Positionen, Richtungen, Farben, Reichweiten und Öffnungswinkel unverändert.
Bis zu drei je Seite, insgesamt maximal zwölf. Die einseitige Quelllage bleibt ausdrücklich eine Grenze.</p>
<p>Nur der HSV-Kandidat verwendet den Exportfaktor 8: Unity-Intensität 60 bleibt als
<code>sourceIntensity</code> erhalten; <code>intensity</code> = 480. Die unveränderte
Browserformel lautet <code>intensity × 8 × min(4, sqrt(Gruppengröße))</code>.
Erneute Kalibrierung rechnet immer von <code>sourceIntensity</code>, nie vom bereits skalierten Wert.
Keine globalen Licht-, Ambient-, Materialemissions- oder Kameraänderungen.</p>
<table><thead><tr><th>Unity-ID</th><th>Originalposition x,y,z (m)</th><th>Flächenabstand (m)</th><th>Quelle</th><th>Export</th><th>Gruppe</th></tr></thead><tbody>{source_rows}</tbody></table>
<h2>Getrennte Zustandsvergleiche</h2>
<p>Acht Aufnahmen mit identischer Kamera, unverändertem Dach und Exposure 1,2.
Tag/Nacht und Flutlicht wurden in jeder Variante unabhängig in derselben Szene geschaltet.
Beide Flutlicht-aus-Vergleiche sind byteidentisch. Alle tatsächlichen SpotLight-Positionen,
Ziele, Winkel, Reichweiten und Intensitäten wurden gegen das Manifest geprüft.</p>
{''.join(pairs)}
<h2>Bildmessung und Grenzen</h2>
<p>Im festen inneren Bildausschnitt (320,380)–(900,600) steigt die mittlere sRGB-Bildhelligkeit nachts mit Flutlicht
von {measurements['baseline-night-on']['sampleMeanSRGBLuma']:.2f} auf
{measurements['candidate-night-on']['sampleMeanSRGBLuma']:.2f} ({ratio:.2f}×).
Das ist eine Bildmessung nach Tonemapping, kein Luxwert, kein Nachweis photometrischer Gleichmäßigkeit und kein Hardware-Leistungstest.
In der gewählten Nachtaufnahme sind {measurements['candidate-night-on']['nearWhiteRGB250Fraction']:.5%}
der Pixel in allen drei Kanälen ≥250.</p>
<p>Die optisch stärkere Teststufe 16 wurde nicht gewählt. Die nicht belegte Gegenüberseite wird nicht durch
verschobene Leuchten oder zusätzliche Fülllichter kaschiert. Unity-Lightmaps und Originalshader werden weiterhin nicht vollständig rekonstruiert.
Es wurden keine Dachschatten-Aussagen aus diesen Bildern abgeleitet.</p>
<h2>Unverändert und überprüfbar</h2>
<p>Registry, ursprüngliches Prüfpaket, Geometrie, Texturen, Kameravertrag, Stadionökonomie, Datenbank und andere Stadien unverändert.
Keine Assets hochgeladen, keine Produktion veröffentlicht. Das vorhandene Registrierwerkzeug verweigert das automatische
Ersetzen eines bestehenden Eintrags; eine spätere Aktivierung benötigt einen ausdrücklich freigegebenen Versionswechsel
mit vorheriger dauerhafter Asset-Prüfung.</p>
<p>Bundle-SHA256: <code>{candidate['sourceSha256']}</code><br>
Geometrie-SHA256: <code>{candidate['geometrySha256']}</code><br>
Ausgangsmanifest-SHA256: <code>{summary['baselineManifestSha256']}</code></p>
<p>Vollständige Einzelbelege: <code>light-audit.json</code>, <code>light-audit.csv</code>,
<code>views/render-evidence.json</code>, <code>measurements.json</code>; versioniertes Asset-Paket unter <code>package/</code>.</p>
</html>"""
    (study / "pruefbericht.html").write_text(document)
    (study / "measurements.json").write_text(json.dumps(measurements, indent=2)+"\n")
    with (study / "light-audit.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "name", "x", "y", "z", "vertex_distance_m",
                         "surface_distance_m", "vertex_rejections", "surface_rejections",
                         "nearest_triangle_index"])
        for row in audit["candidates"]:
            writer.writerow([row["id"], row["name"], *row["position"],
                             row["vertexDistance"], row["meshDistance"],
                             "|".join(row["vertexRejections"]), "|".join(row["surfaceRejections"]),
                             row["nearestLampMesh"]["triangleIndex"]])
    # Package contains data/assets/evidence only, not application source code.
    with zipfile.ZipFile(study / "hsv-nacht-pruefpaket.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(study.rglob("*")):
            if file.is_file() and file.suffix != ".zip":
                archive.write(file, file.relative_to(study))
    print(json.dumps({"verifiedStates": 8, "candidateVersion": candidate["assetVersion"],
                      "sampleLumaRatio": ratio, "report": str(study / "pruefbericht.html")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    report(parser.parse_args().study)
