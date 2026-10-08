"""Build user-facing prompts, geometric masks, OSM references and a ZIP."""
import base64
import html
import json
import math
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "attached_assets/higgsfield_stadium_pack"
SIZE = (1880, 940)
FONT = ImageFont.load_default(size=22)
SMALL = ImageFont.load_default(size=16)

PLACES = {
    "dortmund": {
        "name": "Dortmund · SIGNAL IDUNA PARK",
        "stadium_name": "SIGNAL IDUNA PARK",
        "context": """A photorealistic, restrained Westphalian urban sports-park environment in Dortmund, Germany: real-world sports and exhibition grounds, broad paved access areas, ordinary asphalt service roads, parking areas and deciduous tree groups. Use the supplied OpenStreetMap/site references for the regional context. The separate historic Stadion Rote Erde is east of the main site; Westfalenhalle and exhibition grounds are north/northeast, not directly attached to the main stand. Those separate neighboring facilities may appear only where supported by the site reference and the chosen view; do not force every landmark into this close framing. No mountain backdrop, Alpine landscape, ocean, futuristic skyline or dense decorative forest. Do not invent legible advertising or logos.""",
        "links": [
            ("BVB · Anreise und offizielle Umfeldkarte", "https://www.bvb.de/de/de/signal-iduna-park/stadionbesuch/anreise.html"),
            ("OSM · Stadionstandort", "https://www.openstreetmap.org/way/17235929"),
        ],
    },
    "elversberg": {
        "name": "Elversberg · URSAPHARM-Arena",
        "stadium_name": "Ursapharm-Arena",
        "context": """A photorealistic small-town Saarland sports-ground environment around the Kaiserlinde site in Elversberg, Germany: modest local streets and access paving, nearby low-rise houses with ordinary pitched roofs, parking and service areas, and mixed deciduous woodland with gentle terrain. The club's official site places the ground and fanshop at Lindenstrasse 5, 66583 Elversberg. Use the supplied OpenStreetMap/site references for the actual relative pattern of houses, roads and woodland. No city skyline, Dortmund exhibition halls, huge urban boulevards, ocean, Alpine peaks, exaggerated mountain valley, invented major landmark or new planned development treated as existing. Do not invent legible signs or logos.""",
        "links": [
            ("SV Elversberg · offizieller Standort", "https://sv07elversberg.de/ursapharm-arena/stadionordnung/"),
            ("OSM · Stadionstandort", "https://www.openstreetmap.org/way/1154632806"),
        ],
    },
}

COMMON = """Create a still background plate for a football-manager game, not a finished stadium picture.
The first uploaded image is 03_empty_site_camera.png. It is the PRIMARY camera and composition reference. Keep its projected green 105 x 68 metre pitch EXACTLY in the same pixels, with the same shape and perspective. Do not create or resize a second pitch.
The optional 01_camera_reference.png explains the 3D model alignment only. Do NOT copy its stadium into the final image. The main club stadium, stands, roofs, floodlight masts, scoreboards, crowds, players, ball and field-side game props must be ABSENT from the background plate. Leave the entire main-stadium site free of buildings and trees so our real, expandable 3D stadium can be rendered there later. Keep a natural, low-detail grass/gravel/service-paving transition within the site; no recognizable stadium-shaped seating terraces.
Use 05_environment_edit_mask.png as the editing-area guide: WHITE is the environment that may be edited, BLACK is the protected game field. If the tool uses the opposite mask polarity, invert it. The separate 02_stadium_silhouette.png shows the rendered main-stadium geometry to exclude, not a stencil to reconstruct.
Keep the fixed elevated touchline-side camera: height 98 metres, 76 metres behind the near touchline, downward optical-axis angle 44 degrees, no roll. Reference framing is authoritative over text camera approximations. This is a close, field-first oblique view, NOT a top-down satellite view, NOT a distant aerial panorama and NOT a low eye-level stadium shot. The camera looks downward: do not add a horizon strip, sky band or mountains to the top edge.
Final canvas: 1880 x 940 pixels, exactly 2:1, identical crop and camera registration to the primary image. No borders, captions, UI, watermarks or contact-sheet panels. If a different native image ratio is unavoidable, preserve the reference content with canvas extension/outpainting; do not crop or stretch it.
The north-up OSM guide is a separate geography reference, not the output camera. Mesh-to-map compass orientation has not been independently surveyed. Do not claim a survey-accurate reconstruction or guess a missing absolute bearing. Keep unverified detail restrained.
"""

NEGATIVE = """main stadium, grandstands, stand roof, floodlight mast, stadium bowl, duplicate pitch, resized pitch, new perspective, zoom change, camera roll, fisheye lens, visible skyline band, sky strip, mountains, ocean, neon fantasy, city skyscrapers, invented landmark, legible text, logo, watermark, interface, border, split-screen, football players, ball, crowds"""


def masks_and_overlay(folder, camera):
    corners = camera["corners"]
    points = [(p["x"], p["y"]) for p in corners]
    keep = Image.new("L", SIZE, 0)
    draw = ImageDraw.Draw(keep)
    draw.polygon(points, fill=255)
    draw.line(points + [points[0]], fill=255, width=6)
    keep.save(folder / "04_keep_pitch_mask.png")
    edit = keep.point(lambda value: 255 - value)
    edit.save(folder / "05_environment_edit_mask.png")
    overlay = Image.open(folder / "03_empty_site_camera.png").convert("RGB")
    draw = ImageDraw.Draw(overlay)
    draw.line(points + [points[0]], fill="#22e6ff", width=4)
    # Camera JSON order is far-right, far-left, near-left, near-right.
    for name, index in [("A", 1), ("B", 0), ("C", 3), ("D", 2)]:
        x, y = points[index]
        draw.ellipse((x-12, y-12, x+12, y+12), fill="#07131c", outline="#22e6ff", width=2)
        draw.text((x+17, y-14), name, fill="#22e6ff", font=FONT)
    overlay.save(folder / "06_pitch_registration_guide.png")
    return {name: [round(points[index][0], 2), round(points[index][1], 2)]
            for name, index in [("A", 1), ("B", 0), ("C", 3), ("D", 2)]}


def osm_map(club, folder):
    source = ROOT / f"stadium_editor/blueprints/v2/{club}.json"
    data = json.loads(source.read_text())
    elements = data["elements"]
    stadium = next(e for e in elements if e.get("tags", {}).get("name") == PLACES[club]["stadium_name"])
    bounds = stadium["bounds"]
    lat = (bounds["minlat"] + bounds["maxlat"]) / 2
    lon = (bounds["minlon"] + bounds["maxlon"]) / 2
    cos_lat = math.cos(math.radians(lat))
    radius = 600 if club == "dortmund" else 450
    image = Image.new("RGB", (1100, 1100), "#e8e6df")
    draw = ImageDraw.Draw(image)
    def pt(p):
        x = (p["lon"]-lon) * 111320 * cos_lat
        y = (p["lat"]-lat) * 111320
        return (550 + x / (radius*2) * 960, 550 - y / (radius*2) * 960)
    for e in elements:
        geom, tags = e.get("geometry", []), e.get("tags", {})
        if len(geom) < 2:
            continue
        points = [pt(p) for p in geom if "lat" in p and "lon" in p]
        if not points or not any(-50 < x < 1150 and -50 < y < 1150 for x, y in points):
            continue
        if tags.get("natural") in ("wood", "scrub") or tags.get("landuse") in ("forest", "grass", "meadow"):
            if len(points) > 2:
                draw.polygon(points, fill="#a7c0a2")
        elif tags.get("building"):
            if len(points) > 2:
                draw.polygon(points, fill="#bdb8ad", outline="#827e74")
        elif tags.get("highway"):
            draw.line(points, fill="#ffffff", width=5)
            draw.line(points, fill="#aba79e", width=1)
        elif tags.get("amenity") == "parking" and len(points) > 2:
            draw.polygon(points, fill="#d2d0c8", outline="#aaa69d")
    poly = [pt(p) for p in stadium["geometry"]]
    draw.polygon(poly, fill="#ddebe7", outline="#12879a", width=4)
    draw.text((25, 15), PLACES[club]["name"], fill="#17343d", font=FONT)
    draw.text((25, 47), "Nord oben · Lagehinweis, nicht kalibrierte Spielkamera", fill="#435552", font=SMALL)
    draw.text((1010, 22), "N", fill="#17343d", font=FONT)
    draw.line([(1060, 58), (1060, 18)], fill="#17343d", width=3)
    draw.polygon([(1060, 12), (1053, 24), (1067, 24)], fill="#17343d")
    draw.text((25, 1035), "Gebäude-Auszug: fehlende Wege/Waldflächen sind keine nachgewiesenen Freiflächen.", fill="#435552", font=SMALL)
    draw.text((25, 1065), "© OpenStreetMap contributors · ODbL · vorhandener Auszug, nicht vermessen", fill="#435552", font=SMALL)
    for e in elements:
        name = e.get("tags", {}).get("name", "")
        if name in ("Stadion Rote Erde", "Westfalenhalle"):
            p = e.get("bounds")
            if p:
                x, y = pt({"lon": (p["minlon"]+p["maxlon"])/2, "lat": (p["minlat"]+p["maxlat"])/2})
                if 0 < x < 900 and 70 < y < 1000:
                    draw.text((x, y), name, font=SMALL, fill="#17343d")
    image.save(folder / "07_local_osm_reference.png")


def main():
    metadata = {"format": list(SIZE), "concept": "cutaway", "generated_backgrounds": False,
                "north_calibration_verified": False, "clubs": {}}
    for club, place in PLACES.items():
        folder = OUT / club
        camera = json.loads((folder / "camera.json").read_text())
        for filename in ["01_camera_reference.png", "02_stadium_silhouette.png", "03_empty_site_camera.png"]:
            assert Image.open(folder / filename).size == SIZE
        points = masks_and_overlay(folder, camera)
        osm_map(club, folder)
        day = COMMON + "\nSITE CONTEXT:\n" + place["context"] + """

DAYLIGHT:
Soft neutral daytime light in Germany, restrained realistic colours, consistent diffuse shadows, crisp useful ground detail without visual clutter. The football pitch remains the main clear open region. Do not beautify this into a resort, mountain landscape or postcard panorama.

NEGATIVE CONSTRAINTS:
""" + NEGATIVE
        night = """Use the APPROVED DAY IMAGE for this club as the only structural base. This is a RELIGHT, not a new scene.
Keep every pixel-level edge of the field, buildings, roofs, roads, curbs, trees and parking geometry registered to the daytime image. Keep exactly the same camera, crop, perspective and 1880 x 940 canvas. Do not regenerate, move, add or remove structures.
Change only the time of day to a restrained realistic German evening/night: dim blue ambient light on ground and trees, a few subtle warm windows and existing ordinary street-light locations ONLY where supported by the daytime/site reference. Do not invent a stadium floodlight installation, light masts, searchlights, beams or stadium light glow; the runtime supplies the real stadium lighting independently.
The MAIN STADIUM remains absent. Do not draw crowds, goalposts, players or a ball. Do not introduce a visible sky band or horizon. Preserve the game field region's exact shape and registration; its final rendered lighting is controlled by the 3D game, not this background.
""" + ("\nElversberg's stadium-light positions are not yet verified: do not invent four corner masts or a glowing stadium site.\n" if club == "elversberg" else "") + "\nNEGATIVE CONSTRAINTS:\n" + NEGATIVE
        (folder / "PROMPT_DAY.txt").write_text(day, encoding="utf-8")
        (folder / "PROMPT_NIGHT.txt").write_text(night, encoding="utf-8")
        metadata["clubs"][club] = {"pitch_pixel_corners": points, "sources": place["links"]}
    (OUT / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    # Standalone HTML: embedded preview images, copyable prompts, no JS/CDN.
    sections = []
    for club, place in PLACES.items():
        pictures = []
        for filename, title in [("01_camera_reference.png", "Echte 3D-Kamerareferenz"),
                                ("03_empty_site_camera.png", "Primäres Higgsfield-Bild"),
                                ("05_environment_edit_mask.png", "Umfeld bearbeiten: Weiß"),
                                ("07_local_osm_reference.png", "Reale Ortslage · Norden oben")]:
            image = Image.open(OUT / club / filename).convert("RGB")
            image.thumbnail((700, 390))
            import io
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=78)
            encoded = base64.b64encode(buffer.getvalue()).decode()
            pictures.append(f'<figure><img src="data:image/jpeg;base64,{encoded}" alt="{html.escape(title)}"><figcaption>{title}</figcaption></figure>')
        prompts = "".join(f'<h3>{mode}</h3><pre>{html.escape((OUT/club/file).read_text())}</pre>'
                          for mode, file in [("Tag-Prompt", "PROMPT_DAY.txt"), ("Nacht-Prompt — erst nach Tagfreigabe", "PROMPT_NIGHT.txt")])
        sources = " · ".join(f'<a href="{url}">{html.escape(name)}</a>' for name, url in place["links"])
        sections.append(f'<section><h2>{html.escape(place["name"])}</h2><div class="grid">{"".join(pictures)}</div>{prompts}<p>{sources}</p></section>')
    guide = (ROOT / "docs/stadium/higgsfield-workflow.md").read_text()
    (OUT / "README_DE.md").write_text(guide, encoding="utf-8")
    body = f"""<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Higgsfield · Stadionumfeld</title><style>
body{{margin:0;background:#061019;color:#e5eef3;font:16px/1.55 system-ui}}main{{max-width:1180px;margin:auto;padding:32px 20px}}h1,h2{{line-height:1.2}}h2,a{{color:#54d6e6}}section{{margin:40px 0;border-top:1px solid #24404e;padding-top:25px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}figure{{margin:0}}img{{width:100%;background:#0b1720}}figcaption{{font-size:14px;color:#b8cbd5}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#0d1d28;padding:18px;border-radius:6px;font:13px/1.6 ui-monospace,monospace}}.note{{border-left:3px solid #d9ae70;padding:12px 18px;background:#182329}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}}}</style><main>
<h1>Higgsfield-Paket: Dortmund &amp; Elversberg</h1><p>Feste Schnittansicht · 1880 × 940 · Spielfeld 105 × 68 m</p>
<div class="note">Dies sind echte Renderreferenzen und Bildvorgaben, noch keine generierten Umfeldbilder. Die Ortskarten sind Nord-up-Referenzen; eine vermessene Kompassregistrierung der Unity-Geometrie liegt nicht vor.</div>
<h2>So beginnen</h2><ol><li>Higgsfield Image Editor öffnen, Bildbearbeitung/Image-to-image wählen.</li><li>Pro Verein <b>03_empty_site_camera.png</b> als primäres Bild verwenden.</li><li>Kamerareferenz und Ortskarte als Zusatzreferenzen nutzen. Das Stadion darf nicht kopiert werden.</li><li>Außerhalb des Felds bearbeiten: <b>05_environment_edit_mask.png</b>, weiß = bearbeiten. Maskenrichtung im Werkzeug prüfen; ggf. Pinsel benutzen.</li><li>Tag-Prompt kopieren. Erst eine gute Tagansicht wählen, dann daraus mit Nacht-Prompt ein Nachtbild ableiten.</li><li>Kein Beschnitt/Stretch. Wenn 2:1 nicht verfügbar ist: Leinwand erweitern, nicht das Bild umrahmen oder den Ausschnitt ändern.</li><li>Vier Dateien als dortmund_day/night und elversberg_day/night zurückgeben. Vor Integration Feldregistrierung und Tag-/Nachtkanten prüfen.</li></ol>
<p><a href="https://higgsfield.ai/ai-image-editor">Higgsfield Image Editor</a> · <a href="https://higgsfield.ai/image-editing">Bearbeitung/Inpainting</a></p>
{"".join(sections)}<section><h2>Vollständige Anleitung</h2><pre>{html.escape(guide)}</pre></section></main></html>"""
    (OUT / "START_HERE.html").write_text(body, encoding="utf-8")
    archive = ROOT / "attached_assets/higgsfield_stadium_pack.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(OUT.parent))
    print(f"Prepared {len(list(OUT.rglob('*.png')))} PNG references, four prompts, HTML guide and ZIP.")


if __name__ == "__main__":
    main()
