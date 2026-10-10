"""Build registered, explicitly incomplete Higgsfield inputs; never AI images."""
import argparse
import base64
import html
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from geo_probe_geometry import lonlat_to_scene, polygon_mask
from surroundings_contract import (
    ROOT, CATEGORIES, background_registration, camera_for, file_sha, load_profile,
    read_json, source_geometry, verified_states, visibility_masks,
)

BASE = ROOT / "generated-artifacts/stadium-main-stand-back-probe"
APPROVED = ROOT / "docs/stadium/surroundings-camera.json"
OUT = ROOT / "generated-artifacts/stadium-surroundings"


def mask_image(mask):
    return Image.fromarray((mask.astype(np.uint8)*255))


def prompts(profile):
    features = "; ".join(f"{f['name']}: {f['note']}" for f in profile.get("priority_features", []))
    day = f"""Erstelle eine Tages-Umfeldkulisse für {profile['label']} aus der beigefügten registrierten Vorlage.
Ausgabe exakt 1880 × 940. Die Vorlage bestimmt Ausschnitt, Perspektive und Ortsanordnung; nicht neu zoomen,
drehen, beschneiden, panoramisch erweitern oder einen Horizont hinzufügen. Kamera auf der geografischen
Seite {profile['camera_bearing_deg']}° ab Nord. Das Vereinsstadion und Spielfeld werden später separat gerendert.

KEIN Vereinsstadion im fertigen Hintergrund: keine Tribünen, Dachreste, Fußballfeldlinien, Tore, Zuschauer
oder erfundenen Flutlichtmasten. Die graue Fläche umfasst unbekannten Innenboden und gegebenenfalls
konservativ entfernte Stadion-Fotoanteile samt Schatten; sie ist weder eine vermessene Stadionfläche noch
ein belegter Parkplatz oder Stadtvorplatz. Dort nur ruhigen neutralen Boden ohne erfundene Ortsmerkmale
vorbereiten. Sie ist eine Arbeitsfläche, keine Anweisung, ein Stadion zu malen. Keine Maskenfarben, Texte,
Prüfmarkierungen oder Gebäude-IDs in das Bild übernehmen.

Straßen, kartierte Gebäude und Grünflächen an ihren vorgegebenen Orten belassen. Reale Ortsfotos nur für
Material, Fassaden und Vegetationscharakter verwenden, nicht deren andere Kameraperspektive übernehmen.
Die Originalkarte ist eine Draufsicht, nicht die Zielkamera. Bei schematischen Karten keine Luftfotoqualität
als schon vorhandenen Beleg behandeln. Höhenhüllen sind Annäherungen auf flachem Bezugsniveau, keine echten
Dachformen. Keine unbekannte Höhe, Hanglage oder Waldkante als exakte Geografie erfinden.
Relevante Objekte: {features or 'Nur tatsächlich sichtbare, durch die Quellen belegte Ortsmerkmale.'}

Bildziel: natürliches Tageslicht, zurückhaltende Ortskulisse, keine zusätzliche Stadtpanorama-Komposition.
Bei unzureichender Vorlage ist dies ein Entwurf zur Prüfung, kein vermessenes oder freigegebenes Bild.
Die Kontrollmasken sind separate Hilfen; ein Prompt garantiert keinen Pixelschutz.
"""
    night = f"""Leite die Nachtfassung für {profile['label']} ausschließlich aus dem zuvor abgenommenen Tagesbild ab.
Exakt 1880 × 940, identischer Bildausschnitt. Gebäude-, Straßen-, Gelände- und Baumkanten bleiben an denselben
Pixelpositionen. Kein neues Layout, Zoom, Horizont, neu erfundene Architektur oder andere Baumverteilung.
Nur Beleuchtung und Atmosphäre ändern. Kein Vereinsstadion, Spielfeld, Tribünen, Dach oder Flutlichtmasten
hinzufügen. Das Stadion einschließlich seiner separat belegten Leuchten wird später darüber gerendert.
Keine künstlichen Stadionlichtkegel, Rasenleuchten oder in den Hintergrund eingebrannten Dachschatten malen.
Umfeldleuchten nur nach geeigneten Ortsreferenzen; ohne Beleg eine zurückhaltende unbeleuchtete Nachtfassung,
keine als real ausgegebene Straßen-/Fensterbeleuchtung erfinden.
Keine Prüffarben, Beschriftungen oder Maskenkanten. Die Tag-/Nachtstruktur wird nach der Rückgabe geprüft;
eine bloße Helligkeitsänderung ersetzt die visuelle Qualitätsprüfung nicht.
"""
    for text in (day, night):
        if len(text) > 15000:
            raise ValueError("Higgsfield prompt exceeds 15000 characters")
    return day, night


def add_height_reference(profile, camera, geometry, template, out):
    path = profile.get("height_evidence")
    if not path:
        return {"status": "not_available", "reason": "Keine räumliche Höhenreferenz vorhanden."}
    inputs_path = ROOT / path
    inputs = read_json(inputs_path)  # A configured but missing source must fail.
    for key in ("format", "position", "projection", "worldInverse", "corners"):
        if inputs["camera"][key] != camera[key]:
            raise ValueError("Height evidence belongs to another camera")
    for source, sha in inputs["provenance"]["sha256"].items():
        if file_sha(ROOT / source) != sha:
            raise ValueError(f"Height source changed: {source}; rebuild height inputs")
    render = read_json(inputs_path.parent / "render_verification.json")
    if render["camera"] != inputs["camera"]:
        raise ValueError("Height render/input camera differs")
    width, height = camera["format"]
    rgba = np.fromfile(inputs_path.parent / "environment_only.rgba", dtype=np.uint8)
    if rgba.size != width*height*4:
        raise ValueError("Missing or truncated environment-only depth pass")
    rgb = rgba.reshape(height, width, 4)[::-1, :, :3].astype(np.uint32)
    ids = rgb[:, :, 0] + 256*rgb[:, :, 1] + 65536*rgb[:, :, 2]
    reference = np.asarray(template).copy()
    shape_mask = (ids != 0) & ~geometry["pitch"]
    if np.any(ids > 2*len(render["objects"])):
        raise ValueError("Unexpected stadium/diagnostic geometry in environment-only pass")
    reference[shape_mask & (ids % 2 == 1)] = (184, 138, 207)
    reference[shape_mask & (ids % 2 == 0)] = (128, 102, 173)
    Image.fromarray(reference).save(out / "06_conditional_height_reference.png")
    return {"status": "conditional", "file": "06_conditional_height_reference.png",
            "source_sha256": file_sha(inputs_path), "matching": inputs["matching"],
            "provenance": inputs["provenance"],
            "limits": inputs["limits"],
            "interpretation": "Violette Hüllen: bedingte Höhen, keine Originalfassaden; Gelände/Kronen unbekannt."}


def write_guide(out, profile, manifest, day, night):
    def esc(value):
        return html.escape(str(value))
    def image_block(filename, caption):
        data = "data:image/png;base64," + base64.b64encode((out/filename).read_bytes()).decode()
        return f'<section><h2>{esc(caption)}</h2><a download="{filename}" href="{data}">PNG einzeln herunterladen</a><img src="{data}" alt="{esc(caption)}"></section>'
    def download_text(filename, mime):
        data = f"data:{mime};base64," + base64.b64encode((out/filename).read_bytes()).decode()
        return f'<a download="{filename}" href="{data}">{esc(filename)} herunterladen</a>'
    rows = "".join(f"<tr><td>{esc(g['topic'])}</td><td>{esc(g['status'])}</td><td>{esc(g['impact'])}</td></tr>" for g in profile["gaps"])
    blocks = image_block("01_background_reference.png", "1. Stadionfreie registrierte Arbeitsvorlage — noch kein fertiges Bild")
    blocks += image_block("02_unknown_stadium_ground_mask.png", "2. Weiß: unbekannter Boden und Stadionbild-Entfernung, kein belegter Vorplatz")
    blocks += image_block("03_keep_pitch_mask.png", "3. Weiß: geschützte Feldpixel beim späteren Zusammensetzen")
    blocks += image_block("04_evidence_reference.png", "4. Grün: kartierter Außenboden; Rot: entfernte Fotoanteile; Orange/Violett: Höhen/Innenboden offen")
    blocks += image_block("05_original_map.png", "5. Originalkarte: Nord oben, nicht die Zielperspektive")
    if manifest["height_evidence"]["status"] == "conditional":
        blocks += image_block("06_conditional_height_reference.png", "6. Bedingte Höhenhüllen — ohne Stadion, nicht als Fotoreferenz verwenden")
    if profile.get("photo_stadium_removal"):
        blocks += image_block("07_source_stadium_removal_mask.png", "7. Luftfoto-Kontrollmaske: Dach/Fassade/Pylone/Schatten, unabhängig vom Boden-Grundriss")
    refs = "".join(f'<li><a href="{esc(r["url"])}">{esc(r["subject"])}</a> — {esc(r["date"])}; {esc(r["reuse"])}</li>' for r in profile.get("photo_references", []))
    photo_note = (
        "Ein fotografierter Stadionkörper reicht durch Dachüberstand und Bildversatz über seinen Boden-Grundriss hinaus. "
        "Die Luftfoto-Entfernung ist deshalb separat am Quellbild kalibriert. Sie ist keine neue Stadiongrundfläche."
        if profile.get("photo_stadium_removal") else
        "Diese schematische OSM-Vorlage ist kein Luftfoto; die ausgesparte Stadionfläche belegt keinen Innenboden."
    )
    page = f"""<!doctype html><html lang="de"><meta charset="utf-8"><title>{esc(profile['label'])} · Umfeldvorlagen</title>
<style>body{{font:16px/1.55 system-ui;background:#f4f5f6;color:#192430;max-width:1100px;margin:32px auto;padding:0 20px}}img{{width:100%;height:auto}}section{{margin:32px 0}}pre{{white-space:pre-wrap;background:white;padding:20px;border:1px solid #ccd2d8}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:10px;border:1px solid #ccd2d8}}a{{color:#075da0}}.note{{padding:18px;background:#fff3ce}}</style>
<h1>{esc(profile['label'])}: wiederverwendbares Umfeldpaket</h1>
<p class="note"><strong>Vorbereitungsstand, keine Orts-/Bildabnahme.</strong> {esc(profile['reference_notes'])}
Keine KI-Ausgabe und keine Integration. Unbekannte Bereiche sind absichtlich sichtbar.
Kamerabasis: 75 %, Haupttribüne hinten, 1880 × 940; geografische Kameraseite {profile['camera_bearing_deg']}°.</p>
<h2>Ablauf</h2><ol><li>Vorlage und Quellen-/Lückenübersicht prüfen; offene dominante Ortsmerkmale zuerst klären.</li>
<li>Arbeitsvorlage herunterladen. Originalkarte und bedingte Hüllen nur als getrennte Referenzen verwenden.</li>
<li>Tagesentwurf in Higgsfield erstellen. Keine Kontrollfarben oder Masken in das Ergebnis übernehmen.</li>
<li>Tagesbild visuell abnehmen. Erst danach Nacht daraus ableiten, nicht unabhängig neu erzeugen.</li>
<li>Beide Originaldateien zurückgeben. Kamera, Ortsstruktur, Stadionfreiheit, Dachzustände und Ausbau separat prüfen.</li></ol>
<p>Ein Maskenupload oder Prompt gewährleistet keine Registrierung. Bei Drift gezielt registrierte Nacharbeit,
keine unbegrenzte Wiederholung desselben freien Prompts. Unter dem Originalstadion liegt kein belegter Stadtvorplatz.</p>
<p>{photo_note}
Die unveränderte Originalkarte enthält das Quellstadion und dient der Quellenkontrolle, nicht als ungefilterte Bildvorlage.</p>
<h2>Quellen und Lücken</h2><p>{esc(profile['ground_source']['credit'])}</p><table><tr><th>Thema</th><th>Status</th><th>Grenze</th></tr>{rows}</table>
<ul>{refs}</ul><p>Foto-/Vermessungsdatum nicht aus Dienstversionen ableiten; Weiterverwendungsrechte separat prüfen.</p>
<p>{download_text('sources.json', 'application/json')}</p>
<h2>Prompt Tag · {len(day)} Zeichen</h2><p>{download_text('prompt_day.txt', 'text/plain')}</p><pre>{esc(day)}</pre>
<h2>Prompt Nacht · {len(night)} Zeichen</h2><p>{download_text('prompt_night.txt', 'text/plain')}</p><pre>{esc(night)}</pre>{blocks}
<h2>Abnahmematrix</h2><p>Tag/Nacht × Dach an/aus, jeweils Bestand und ein plausibler Ausbauzustand.
Diese Matrix ist definiert, nicht schon bestanden. Nutzerbilder und Ausbau-Render fehlen noch.
Elversbergs fehlendes Flutlicht bleibt separat; die Nachtkulisse ersetzt keine Stadionleuchten.</p>
<p>Registrierung: <code>{manifest['background_registration']}</code>. Sie hängt an Kamera/Ortsrahmen,
nicht am Dach, Budget oder aktuellen Stadionausbau. Geänderte Stadiongeometrie benötigt neue
Verdeckungsnachweise, nicht automatisch neue Hintergrundbilder.</p></html>"""
    (out / "guide.html").write_text(page)


def build_pack(profile_path, base=BASE, output=OUT, approved_path=APPROVED):
    profile = load_profile(profile_path)
    export, states, images = verified_states(profile, base, approved_path)
    camera = camera_for(export)
    geometry = source_geometry(profile, camera)
    out = output / profile["id"]
    out.mkdir(parents=True, exist_ok=True)
    # Remove the whole source stadium site, not just today's visible silhouette.
    unknown = geometry["site"] | geometry["pitch"] | geometry["projected_photo_removal"]
    # Small safety margin only for the photographic removal guide, not visibility counts.
    unknown_margin = np.asarray(mask_image(unknown).filter(ImageFilter.MaxFilter(11))) > 128
    template = geometry["plane"].copy()
    template[unknown_margin] = (104, 112, 119)
    template = Image.fromarray(template)
    template.save(out / "01_background_reference.png")
    mask_image(unknown_margin).save(out / "02_unknown_stadium_ground_mask.png")
    mask_image(geometry["pitch"]).save(out / "03_keep_pitch_mask.png")
    geometry["raster"].save(out / "05_original_map.png")
    if geometry["photo_removal_mask"] is not None:
        geometry["photo_removal_mask"].save(out / "07_source_stadium_removal_mask.png")
    Image.fromarray(geometry["plane"]).save(out / "checks_ground_projection.png")
    status = np.full_like(geometry["plane"], (35, 170, 105))
    status[geometry["site"]] = CATEGORIES["inside_other"]
    status[geometry["cut"]] = CATEGORIES["cut_stand"]
    status[geometry["pitch"]] = CATEGORIES["pitch"]
    status[geometry["projected_photo_removal"] & ~geometry["site"] & ~geometry["pitch"]] = (221, 100, 100)
    # Unknown landmark height is flagged at its real footprint, never moved.
    ways = {e["id"]: e for e in geometry["osm"]["elements"] if e["type"] == "way"}
    for feature in profile.get("priority_features", []):
        way = ways[feature["osm_id"]]
        footprint = polygon_mask(camera, [lonlat_to_scene(geometry["frame"], p["lon"], p["lat"], True) for p in way["geometry"]])
        status[footprint & ~geometry["pitch"]] = (242, 146, 44) if feature["status"] == "unknown" else (161, 123, 203)
    Image.fromarray(status).save(out / "04_evidence_reference.png")
    visibility = {}
    checks = out / "checks"
    checks.mkdir(exist_ok=True)
    for state in states:
        variant = state.get("variant", "day")
        render_file = state["imageEvidence"]["render"]["file"]
        shutil.copyfile(base / render_file, checks / render_file)
        if variant == "day":
            mask_file = state["imageEvidence"]["silhouette"]["file"]
            shutil.copyfile(base / mask_file, checks / mask_file)
            masks = visibility_masks(geometry, images[(state["roof"], "silhouette")])
            stem = "roof" if state["roof"] else "no_roof"
            visibility[stem] = {k: {"pixels": int(m.sum()), "pct": round(float(m.mean()*100), 4)} for k, m in masks.items()}
            for key, mask in masks.items():
                mask_image(mask).save(checks / f"{stem}_{key}_mask.png")
    height = add_height_reference(profile, camera, geometry, template, out)
    day, night = prompts(profile)
    (out / "prompt_day.txt").write_text(day)
    (out / "prompt_night.txt").write_text(night)
    manual = {"day_visually_approved": False, "geographic_structure_reviewed": False,
              "stadium_absent": False, "night_layout_reviewed": False,
              "expansion_visually_reviewed": False, "rights_confirmed": False,
              "reference_limits_accepted": False,
              "reviewer": "", "notes": ""}
    manifest = {
        "version": 1, "club": profile["id"], "label": profile["label"],
        "profile": profile, "camera": camera, "frame": geometry["frame"],
        "background_registration": background_registration(camera, geometry["frame"]),
        "quality": "incomplete_registered_reference_not_verified_photography",
        "ground_provenance": geometry["source_details"],
        "photo_removal": profile.get("photo_stadium_removal"),
        "photo_removal_outside_site_pixels": int((geometry["projected_photo_removal"] & ~geometry["site"]).sum()),
        "height_evidence": height, "visibility": visibility,
        "states": states, "fitted": export["fitted"],
        "source_export_sha256": file_sha(base / "verification.json"),
        "osm_sha256": file_sha(ROOT / profile["osm_file"]),
        "prompt_characters": {"day": len(day), "night": len(night)},
        "source_limits": [
            "Bodenpositionen sind keine Fassaden-/Baumkronen-Sichtbelege.",
            "Stadion-Silhouette dient nur der Prüfung, nicht als dauerhafte Bildaussparung.",
            "Vorhandene Inhaltsnachweise beweisen keine Aktualität sämtlicher Modellquellen.",
            "Diagnostische Komposition nutzt harte Maskenkanten, keine produktive Alpha-Integration.",
        ],
        "acceptance_matrix": [
            {"time": t, "roof": r, "model": m, "status": "awaiting_user_images" if m == "bestand" else "awaiting_expansion_render"}
            for m in ("bestand", "ausbau") for t in ("day", "night") for r in (True, False)
        ],
    }
    (out / "manual_review.example.json").write_text(json.dumps(manual, indent=2, ensure_ascii=False))
    (out / "sources.json").write_text(json.dumps({"ground": profile["ground_source"], "ground_provenance": geometry["source_details"],
        "photos": profile.get("photo_references", []),
        "height": height, "gaps": profile["gaps"]}, indent=2, ensure_ascii=False))
    write_guide(out, profile, manifest, day, night)
    owned = {
        "01_background_reference.png", "02_unknown_stadium_ground_mask.png",
        "03_keep_pitch_mask.png", "04_evidence_reference.png", "05_original_map.png",
        "checks_ground_projection.png", "prompt_day.txt", "prompt_night.txt",
        "manual_review.example.json", "sources.json", "guide.html",
    }
    if height["status"] == "conditional":
        owned.add("06_conditional_height_reference.png")
    if geometry["photo_removal_mask"] is not None:
        owned.add("07_source_stadium_removal_mask.png")
    for state in states:
        owned.add("checks/" + state["imageEvidence"]["render"]["file"])
        if state.get("variant", "day") == "day":
            owned.add("checks/" + state["imageEvidence"]["silhouette"]["file"])
    for stem in ("roof", "no_roof"):
        owned.update(f"checks/{stem}_{key}_mask.png" for key in CATEGORIES)
    # Never attest leftover files from an older run or erase user-added files.
    manifest["files"] = {filename: file_sha(out / filename) for filename in sorted(owned)}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"{profile['label']}: {out}; prompts {len(day)}/{len(night)} Zeichen; unvollständige Ortsreferenz")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", nargs="+", type=Path,
                        default=sorted((ROOT / "docs/stadium/surroundings-profiles").glob("*.json")))
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--approved", type=Path, default=APPROVED)
    args = parser.parse_args()
    for path in args.profiles:
        build_pack(path, args.base, args.output, args.approved)


if __name__ == "__main__":
    main()
