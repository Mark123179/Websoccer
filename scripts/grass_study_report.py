#!/usr/bin/env python3
"""Build a self-contained BLUEPRINT Football Manager grass-study report.

Run from any directory with:
    python scripts/grass_study_report.py

Inputs and outputs live in generated-artifacts/grass-study/ at the workspace
root. The report embeds each source image once and reuses it for all views.
"""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError as exc:  # pragma: no cover - environment-specific diagnostic
    raise SystemExit(
        "Pillow is required to build the comparison sheets. "
        "Install it with: python -m pip install Pillow"
    ) from exc


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
STUDY_DIR = WORKSPACE_ROOT / "generated-artifacts" / "grass-study"
MANIFEST_PATH = STUDY_DIR / "manifest.json"
HTML_PATH = STUDY_DIR / "vergleich.html"
DAY_SHEET_PATH = STUDY_DIR / "vergleich-tag.png"
TOP_SHEET_PATH = STUDY_DIR / "vergleich-draufsicht.png"

OPTIONAL_REFERENCES = {
    "A1-night": ("renders/A1-night.png", "A1 · Nachtlicht"),
    "C2-night": ("renders/C2-night.png", "C2 · Nachtlicht"),
    "A1-elversberg": ("renders/A1-elversberg.png", "A1 · Elversberg"),
    "C2-elversberg": ("renders/C2-elversberg.png", "C2 · Elversberg"),
    "bestand-day": ("renders/bestand-day.png", "Bestand · Tag"),
}

BG = "#071510"
PANEL = "#10251c"
PANEL_ALT = "#142d22"
LINE = "#335342"
TEXT = "#e8f0df"
MUTED = "#aab9a8"
LIME = "#b8d779"
CYAN = "#8cc7c1"
AMBER = "#e2b96f"


def require_file(path: Path) -> bytes:
    if not path.is_file():
        raise FileNotFoundError(f"Erforderliche Eingabedatei fehlt: {path}")
    return path.read_bytes()


def load_manifest() -> list[dict[str, str]]:
    raw = require_file(MANIFEST_PATH)
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Manifest ist kein gültiges UTF-8-JSON: {MANIFEST_PATH}") from exc

    variants = manifest.get("variants") if isinstance(manifest, dict) else None
    if not isinstance(variants, list):
        raise ValueError("manifest.json muss ein Objekt mit einem variants-Array enthalten.")
    if len(variants) != 12:
        raise ValueError(
            f"Erwartet werden genau 12 Varianten für den 12-Kachel-Vergleich; "
            f"gefunden: {len(variants)}."
        )

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, variant in enumerate(variants, start=1):
        if not isinstance(variant, dict):
            raise ValueError(f"Variante {index} muss ein JSON-Objekt sein.")
        missing = [key for key in ("id", "patternLabel", "toneLabel", "wearLabel", "group")
                   if not isinstance(variant.get(key), str) or not variant[key].strip()]
        if missing:
            raise ValueError(f"Variante {index} hat fehlende oder leere Felder: {', '.join(missing)}.")
        item = {key: variant[key].strip() for key in
                ("id", "patternLabel", "toneLabel", "wearLabel", "group")}
        if item["id"] in seen:
            raise ValueError(f"Varianten-ID ist doppelt vorhanden: {item['id']}")
        if Path(item["id"]).name != item["id"] or item["id"] in {".", ".."}:
            raise ValueError(f"Ungültige Varianten-ID (nur Dateiname erlaubt): {item['id']!r}")
        seen.add(item["id"])
        normalized.append(item)
    return normalized


def encode_data_url(path: Path, mime: str) -> str:
    payload = base64.b64encode(require_file(path)).decode("ascii")
    return f"data:{mime};base64,{payload}"

def encode_view(path: Path) -> str:
    """Full pixel dimensions, compact report previews; original PNGs stay in the package."""
    require_file(path)
    buffer = io.BytesIO()
    with Image.open(path) as image:
        image.convert("RGB").save(buffer, "WEBP", quality=90, method=5)
    return "data:image/webp;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def load_assets(variants: list[dict[str, str]]) -> dict[str, Any]:
    assets: dict[str, Any] = {"variants": [], "references": []}
    for variant in variants:
        variant_assets = dict(variant)
        variant_assets["day"] = encode_view(STUDY_DIR / "renders" / f"{variant['id']}-day.png")
        variant_assets["top"] = encode_view(STUDY_DIR / "top" / f"{variant['id']}.png")
        variant_assets["texture"] = encode_data_url(
            STUDY_DIR / "textures" / f"{variant['id']}.webp", "image/webp"
        )
        assets["variants"].append(variant_assets)

    for key, (relative_path, label) in OPTIONAL_REFERENCES.items():
        path = STUDY_DIR / relative_path
        if path.is_file():
            assets["references"].append({
                "key": key,
                "label": label,
                "src": encode_view(path),
            })
    return assets


def safe_json(value: Any) -> str:
    """JSON safe to place in a script element without HTML parser surprises."""
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c")
            .replace(">", "\\u003e").replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))


def build_html(assets: dict[str, Any]) -> str:
    data = safe_json(assets)
    return HTML_DOCUMENT.replace("__STUDY_DATA__", data)


def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ] if bold else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def fit_image(image_path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(image_path).convert("RGBA")
    return ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont,
              max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def draw_comparison_sheet(variants: list[dict[str, str]], view: str, output: Path) -> None:
    cols, rows = 4, 3
    tile_w, tile_h = 1000, 680
    margin, gutter, header_h = 74, 22, 128
    sheet = Image.new(
        "RGB",
        (margin * 2 + cols * tile_w + (cols - 1) * gutter,
         header_h + margin + rows * tile_h + (rows - 1) * gutter + margin),
        BG,
    )
    draw = ImageDraw.Draw(sheet)
    title_font = find_font(46, bold=True)
    sub_font = find_font(22)
    id_font = find_font(27, bold=True)
    caption_font = find_font(22)
    title = "RASENSTUDIE  /  " + ("TAGANSICHT" if view == "day" else "NEUTRALE DRAUFSICHT")
    draw.text((margin, 28), title, fill=TEXT, font=title_font)
    draw.text(
        (margin, 88),
        "BLUEPRINT Football Manager  ·  12 Varianten  ·  identische Kachelgröße und Beleuchtung",
        fill=MUTED, font=sub_font,
    )

    for index, variant in enumerate(variants):
        row, col = divmod(index, cols)
        x = margin + col * (tile_w + gutter)
        y = header_h + row * (tile_h + gutter)
        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=10,
                               fill=PANEL, outline=LINE, width=2)
        draw.rectangle((x + 1, y + 1, x + tile_w - 1, y + 8), fill=LIME)
        image_path = (STUDY_DIR / "renders" / f"{variant['id']}-day.png"
                      if view == "day" else STUDY_DIR / "top" / f"{variant['id']}.png")
        preview = fit_image(image_path, (tile_w - 44, 440))
        px = x + (tile_w - preview.width) // 2
        py = y + 22 + (440 - preview.height) // 2
        sheet.paste(preview, (px, py), preview)
        draw.line((x + 24, y + 476, x + tile_w - 24, y + 476), fill=LINE, width=2)
        draw.text((x + 28, y + 493), variant["id"], fill=CYAN, font=id_font)
        label = (
            f"Muster: {variant['patternLabel']}  ·  Grünton: {variant['toneLabel']}  ·  "
            f"Abnutzung: {variant['wearLabel']}"
        )
        lines = wrap_text(draw, label, caption_font, tile_w - 56)
        for line_index, line in enumerate(lines[:3]):
            draw.text((x + 28, y + 536 + line_index * 30), line, fill=TEXT, font=caption_font)
        draw.text((x + 28, y + tile_h - 36), f"GRUPPE  {variant['group']}",
                  fill=AMBER, font=find_font(16, bold=True))

    sheet.save(output, format="PNG", optimize=True)


HTML_DOCUMENT = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#071510">
<title>Rasenstudie · BLUEPRINT Football Manager</title>
<style>
:root{color-scheme:dark;--bg:#071510;--surface:#10251c;--surface2:#142d22;--edge:#335342;--text:#e8f0df;--muted:#aab9a8;--faint:#788a7a;--lime:#b8d779;--cyan:#8cc7c1;--amber:#e2b96f;--mono:"SFMono-Regular",Consolas,"Liberation Mono",monospace;--sans:"Aptos","Segoe UI",system-ui,sans-serif}
*{box-sizing:border-box}html{min-width:320px;scroll-behavior:smooth;background:var(--bg)}body{margin:0;min-height:100dvh;color:var(--text);font:15px/1.55 var(--sans);background:radial-gradient(ellipse at 76% -12%,#25432b 0,transparent 36%),linear-gradient(180deg,#0c1b13 0,var(--bg) 500px)}
button,select,a{font:inherit}button,select{color:inherit}.wrap{width:min(1440px,100%);margin:auto;padding:clamp(18px,4vw,52px) clamp(14px,3vw,44px) 48px}
.mast{display:flex;align-items:center;justify-content:space-between;gap:20px;padding-bottom:22px;border-bottom:1px solid var(--edge)}
.brand{display:flex;align-items:center;gap:12px;color:var(--text);text-decoration:none;font-weight:800;letter-spacing:.14em;font-size:12px}.mark{display:grid;place-items:center;width:35px;height:35px;border:1px solid var(--lime);color:var(--lime);font:700 15px var(--mono);transform:skew(-7deg)}.brand small{display:block;margin-top:4px;color:var(--muted);font:500 9px var(--mono);letter-spacing:.18em}
.status{display:flex;align-items:center;gap:9px;color:var(--muted);font:500 10px var(--mono);letter-spacing:.1em;text-transform:uppercase}.status:before{content:"";width:7px;height:7px;border-radius:50%;background:var(--lime);box-shadow:0 0 0 4px #b8d77920}
.hero{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(250px,.65fr);gap:40px;align-items:end;padding:clamp(40px,7vw,82px) 0 38px}.eyebrow,.section-kicker{margin:0;color:var(--lime);font:600 10px/1.4 var(--mono);letter-spacing:.17em;text-transform:uppercase}.hero h1{margin:12px 0 0;font-size:clamp(42px,7.4vw,94px);line-height:.91;letter-spacing:-.075em;font-weight:760}.hero h1 span{color:var(--lime)}.hero-copy{max-width:420px;color:var(--muted);font-size:14px;line-height:1.75}.hero-copy p{margin:0 0 16px}.stamp{display:inline-flex;align-items:center;gap:9px;padding:9px 11px;border:1px solid #b8d77955;background:#b8d7790c;color:#deedbc;font:600 10px var(--mono);letter-spacing:.07em;text-transform:uppercase}.stamp:before{content:"";width:6px;height:6px;border-radius:50%;background:var(--lime)}
.disclaimer{display:grid;grid-template-columns:auto 1fr;gap:14px;align-items:start;margin:0 0 28px;padding:17px 19px;border:1px solid #e2b96f66;background:#e2b96f0b}.disclaimer strong{color:var(--amber);font:700 10px var(--mono);letter-spacing:.1em;text-transform:uppercase}.disclaimer p{margin:0;color:#dfd9c8;font-size:12px;line-height:1.65}
.section-head{display:flex;justify-content:space-between;align-items:end;gap:20px;margin:36px 0 14px}.section-head h2{margin:5px 0 0;font-size:clamp(21px,3vw,30px);letter-spacing:-.045em}.section-head p{margin:0;color:var(--muted);font:10px/1.5 var(--mono);letter-spacing:.08em;text-transform:uppercase}
.controls{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;padding:16px;border:1px solid var(--edge);background:var(--surface);margin-bottom:14px}.control label{display:block;margin:0 0 8px;color:var(--muted);font:600 9px var(--mono);letter-spacing:.13em;text-transform:uppercase}.control select{width:100%;min-height:44px;padding:0 12px;border:1px solid #52705a;border-radius:2px;background:#0a1b12;color:var(--text);outline:none}.control select:focus-visible,button:focus-visible,a:focus-visible{outline:2px solid var(--lime);outline-offset:3px}
.compare{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.view{min-width:0;border:1px solid var(--edge);background:var(--surface)}.view-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 16px;border-bottom:1px solid var(--edge)}.view-head h3{margin:0;font-size:14px;letter-spacing:-.02em}.view-head span{color:var(--cyan);font:10px var(--mono);letter-spacing:.08em;text-transform:uppercase}
.image-stage{display:grid;place-items:center;aspect-ratio:16/9;min-height:210px;overflow:hidden;background:radial-gradient(ellipse at center,#20372a,#0a1710 72%)}.image-stage img{display:block;width:100%;height:100%;object-fit:contain}.caption{min-height:86px;padding:13px 15px;border-top:1px solid var(--edge)}.caption strong{display:block;margin-bottom:4px;color:var(--text);font-size:13px}.caption p{margin:0;color:var(--muted);font-size:11px;line-height:1.6}.caption b{color:var(--lime);font-weight:600}
.downloads{display:flex;flex-wrap:wrap;gap:8px;padding:12px 15px;border-top:1px solid var(--edge);background:#0b1b12}.download{display:inline-flex;align-items:center;min-height:32px;padding:0 10px;border:1px solid #52705a;color:#c6d5c4;text-decoration:none;font:10px var(--mono);transition:color .16s ease,border-color .16s ease,background .16s ease}.download:hover{color:var(--lime);border-color:var(--lime);background:#b8d7790d}
.detail{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(220px,.5fr);gap:14px;margin-top:14px}.texture-panel,.notes-panel{border:1px solid var(--edge);background:var(--surface)}.texture-panel header,.notes-panel header{padding:13px 16px;border-bottom:1px solid var(--edge)}.texture-panel h3,.notes-panel h3{margin:0;font-size:13px}.texture-body{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center;padding:14px}.texture-body img{display:block;width:100%;max-height:240px;object-fit:contain;background:#09170f}.notes-panel p{margin:13px 16px;color:var(--muted);font-size:11px;line-height:1.7}.notes-panel strong{color:var(--amber)}
.overview{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.tile{min-width:0;border:1px solid var(--edge);background:var(--surface);cursor:pointer;transition:border-color .16s ease,transform .16s ease,background .16s ease}.tile:hover{border-color:var(--lime);transform:translateY(-2px)}.tile[aria-pressed="true"]{border-color:var(--lime);background:#172f20;box-shadow:inset 0 3px 0 var(--lime)}.tile img{display:block;width:100%;aspect-ratio:16/9;object-fit:contain;background:#0a1710}.tile-copy{padding:10px 11px 12px}.tile-id{display:flex;justify-content:space-between;gap:8px;color:var(--cyan);font:600 10px var(--mono)}.tile-copy p{margin:7px 0 0;color:var(--muted);font-size:10px;line-height:1.5}.tile-copy b{color:var(--text);font-weight:600}
.references{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.reference{margin:0;border:1px solid var(--edge);background:var(--surface)}.reference img{display:block;width:100%;aspect-ratio:16/9;object-fit:contain;background:#0a1710}.reference figcaption{padding:9px 11px;color:var(--muted);font:10px var(--mono)}
.sheet-links{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}.sheet-links a{padding:10px 13px;border:1px solid var(--edge);background:var(--surface);color:var(--text);text-decoration:none;font:10px var(--mono);letter-spacing:.04em}.sheet-links a:hover{border-color:var(--lime);color:var(--lime)}
footer{display:flex;justify-content:space-between;gap:16px;margin-top:40px;padding-top:14px;border-top:1px solid var(--edge);color:var(--faint);font:9px var(--mono);letter-spacing:.08em;text-transform:uppercase}
@media(max-width:850px){.hero{grid-template-columns:1fr;gap:18px}.hero-copy{max-width:640px}.detail{grid-template-columns:1fr}.overview{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:620px){.mast{align-items:flex-start}.status{max-width:130px;text-align:right;line-height:1.5}.controls,.compare{grid-template-columns:1fr}.view+.view{margin-top:0}.image-stage{min-height:190px}.overview{grid-template-columns:repeat(2,minmax(0,1fr))}.references{grid-template-columns:1fr}.section-head{align-items:flex-start;flex-direction:column}.texture-body{grid-template-columns:1fr}footer{flex-direction:column}.disclaimer{grid-template-columns:1fr;gap:7px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*:before,*:after{transition-duration:.01ms!important}}
</style>
</head>
<body>
<main class="wrap">
  <header class="mast">
    <div class="brand"><span class="mark" aria-hidden="true">B</span><span>BLUEPRINT<small>FOOTBALL MANAGER</small></span></div>
    <div class="status">Isolierte Materialstudie</div>
  </header>
  <section class="hero" aria-labelledby="title">
    <div><p class="eyebrow">SPIELFELD · MATERIAL · SICHTPRÜFUNG</p><h1 id="title">Gras in<br><span>zwölf Lesarten.</span></h1></div>
    <div class="hero-copy"><p>Ein kontrollierter Blick auf Muster, Grünton und Abnutzung. Die Tagesansichten teilen dieselben Lichtbedingungen; die Draufsicht löst die Geometrie aus der Perspektive.</p><span class="stamp">12 Varianten · gleicher Maßstab</span></div>
  </section>
  <aside class="disclaimer" aria-label="Hinweis zur isolierten Studie"><strong>Isolierte Studie</strong><p>Diese Vorschau dient ausschließlich dem visuellen Materialvergleich. Sie nimmt <b>keine Produktionsänderungen</b> vor und ist weder eine Freigabe noch eine Aussage über den Einsatz im Spiel.</p></aside>

  <section aria-labelledby="compare-title">
    <div class="section-head"><div><p class="section-kicker">01 / MATERIAL DIREKT VERGLEICHEN</p><h2 id="compare-title">Gleiche Beleuchtung. Zwei Oberflächen.</h2></div><p>Ansichtstag · identische Bildfläche</p></div>
    <div class="controls" aria-label="Varianten für den Vergleich wählen">
      <div class="control"><label for="variant-a">Linke Vergleichsfläche</label><select id="variant-a"></select></div>
      <div class="control"><label for="variant-b">Rechte Vergleichsfläche</label><select id="variant-b"></select></div>
    </div>
    <div class="compare">
      <article class="view"><header class="view-head"><h3 id="day-name-a">Variante</h3><span>Tag · Vergleich A</span></header><div class="image-stage"><img id="day-image-a" alt=""></div><div class="caption" id="day-caption-a"></div><div class="downloads" id="downloads-a"></div></article>
      <article class="view"><header class="view-head"><h3 id="day-name-b">Variante</h3><span>Tag · Vergleich B</span></header><div class="image-stage"><img id="day-image-b" alt=""></div><div class="caption" id="day-caption-b"></div><div class="downloads" id="downloads-b"></div></article>
    </div>
    <div class="section-head"><div><p class="section-kicker">02 / GEOMETRIE OHNE KAMERA-EFFEKT</p><h2>Neutrale Draufsicht</h2></div><p>Top-Render · gleiche Darstellung</p></div>
    <div class="compare">
      <article class="view"><header class="view-head"><h3 id="top-name-a">Variante</h3><span>Draufsicht · A</span></header><div class="image-stage"><img id="top-image-a" alt=""></div><div class="caption" id="top-caption-a"></div></article>
      <article class="view"><header class="view-head"><h3 id="top-name-b">Variante</h3><span>Draufsicht · B</span></header><div class="image-stage"><img id="top-image-b" alt=""></div><div class="caption" id="top-caption-b"></div></article>
    </div>
    <div class="detail">
      <article class="texture-panel"><header><h3 id="texture-title">Quelldatei und Vollauflösung</h3></header><div class="texture-body"><img id="texture-image" alt=""><div class="downloads" id="texture-download"></div></div></article>
      <aside class="notes-panel"><header><h3>Prüfhinweis</h3></header><p>Vergleiche bevorzugt benachbarte Varianten mit nur einem wechselnden Merkmal. Renderer-Ausgabe und Texturdatei bleiben separat abrufbar; die Anzeige passt Vorschauen lediglich in einen gemeinsamen Bildrahmen ein.</p></aside>
    </div>
  </section>

  <section aria-labelledby="overview-title">
    <div class="section-head"><div><p class="section-kicker">03 / ALLE MATERIALSTÄNDE</p><h2 id="overview-title">Zwölf auf einen Blick</h2></div><p>Auswahl anklicken, um Vergleich A zu setzen</p></div>
    <div class="overview" id="overview"></div>
  </section>
  <section id="references-section" hidden aria-labelledby="reference-title">
    <div class="section-head"><div><p class="section-kicker">KONTEXTBILDER</p><h2 id="reference-title">Optionale Referenzen</h2></div><p>Zusätzliche Render, keine Varianten</p></div>
    <div class="references" id="references"></div>
  </section>
  <nav class="sheet-links" aria-label="Vergleichsbögen herunterladen">
    <a id="sheet-day" download="vergleich-tag.webp">Vergleichsbogen Tag</a>
    <a id="sheet-top" download="vergleich-draufsicht.webp">Vergleichsbogen Draufsicht</a>
  </nav>
  <footer><span>BLUEPRINT · Materialprüfung</span><span>Isolierter Vergleich · keine Produktionsänderung</span></footer>
</main>
<script>
const STUDY=__STUDY_DATA__;
const byId=new Map(STUDY.variants.map(v=>[v.id,v]));
const selectA=document.getElementById("variant-a");
const selectB=document.getElementById("variant-b");
const caption=v=>`<p><b>Muster:</b> ${escapeText(v.patternLabel)} · <b>Grünton:</b> ${escapeText(v.toneLabel)} · <b>Abnutzung:</b> ${escapeText(v.wearLabel)}</p>`;
function escapeText(value){return String(value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function optionLabel(v){return `${v.id} — ${v.patternLabel} / ${v.toneLabel} / ${v.wearLabel}`;}
function downloadLink(label,src,name){const a=document.createElement("a");a.className="download";a.href=src;a.download=name;a.textContent=label;return a;}
function setSide(side,v){
  document.getElementById(`day-name-${side}`).textContent=optionLabel(v);
  const day=document.getElementById(`day-image-${side}`);day.src=v.day;day.alt=`Tagansicht ${v.id}: ${v.patternLabel}, ${v.toneLabel}, ${v.wearLabel}`;
  document.getElementById(`day-caption-${side}`).innerHTML=caption(v);
  const top=document.getElementById(`top-image-${side}`);top.src=v.top;top.alt=`Neutrale Draufsicht ${v.id}: ${v.patternLabel}, ${v.toneLabel}, ${v.wearLabel}`;
  document.getElementById(`top-name-${side}`).textContent=optionLabel(v);
  document.getElementById(`top-caption-${side}`).innerHTML=caption(v);
  const downloads=document.getElementById(`downloads-${side}`);downloads.replaceChildren(
    downloadLink("Tagbild · WEBP",v.day,`${v.id}-day.webp`),
    downloadLink("Draufsicht · WEBP",v.top,`${v.id}-top.webp`),
    downloadLink("Textur · WEBP",v.texture,`${v.id}.webp`)
  );
}
function setPrimary(v){
  document.getElementById("texture-title").textContent=`Texturdatei · ${v.id}`;
  const texture=document.getElementById("texture-image");texture.src=v.texture;texture.alt=`Vollauflösende Materialtextur ${v.id}`;
  const links=document.getElementById("texture-download");links.replaceChildren(downloadLink("Textur in Vollauflösung herunterladen",v.texture,`${v.id}.webp`));
  document.querySelectorAll(".tile").forEach(tile=>tile.setAttribute("aria-pressed",String(tile.dataset.id===v.id)));
}
function sync(){
  const a=byId.get(selectA.value),b=byId.get(selectB.value);
  setSide("a",a);setSide("b",b);setPrimary(a);
}
for(const v of STUDY.variants){
  for(const select of [selectA,selectB]){const option=document.createElement("option");option.value=v.id;option.textContent=optionLabel(v);select.append(option);}
}
selectA.value=STUDY.variants[0].id;selectB.value=STUDY.variants[1].id;
selectA.addEventListener("change",sync);selectB.addEventListener("change",sync);
const overview=document.getElementById("overview");
for(const v of STUDY.variants){
  const button=document.createElement("button");button.type="button";button.className="tile";button.dataset.id=v.id;button.setAttribute("aria-pressed","false");button.setAttribute("aria-label",`Variante ${optionLabel(v)} als Vergleich A auswählen`);
  const img=document.createElement("img");img.src=v.day;img.alt="";img.loading="lazy";
  const copy=document.createElement("div");copy.className="tile-copy";
  const id=document.createElement("div");id.className="tile-id";id.innerHTML=`<span>${escapeText(v.id)}</span><span>${escapeText(v.group)}</span>`;
  const labels=document.createElement("p");labels.innerHTML=caption(v).replace(/^<p>|<\/p>$/g,"");
  copy.append(id,labels);button.append(img,copy);
  button.addEventListener("click",()=>{selectA.value=v.id;sync();document.getElementById("compare-title").scrollIntoView({behavior:"smooth",block:"start"});});
  overview.append(button);
}
if(STUDY.references.length){
  const section=document.getElementById("references-section");section.hidden=false;
  const list=document.getElementById("references");
  for(const ref of STUDY.references){const figure=document.createElement("figure");figure.className="reference";const img=document.createElement("img");img.src=ref.src;img.alt=ref.label;img.loading="lazy";const cap=document.createElement("figcaption");cap.textContent=ref.label;figure.append(img,cap);list.append(figure);}
}
document.getElementById("sheet-day").href=STUDY.sheets.day;
document.getElementById("sheet-top").href=STUDY.sheets.top;
sync();
</script>
</body>
</html>
"""


def main() -> int:
    try:
        variants = load_manifest()
        # Fail before producing partial outputs if any required source is absent.
        assets = load_assets(variants)
        for variant in variants:
            require_file(STUDY_DIR / "renders" / f"{variant['id']}-day.png")
            require_file(STUDY_DIR / "top" / f"{variant['id']}.png")
        STUDY_DIR.mkdir(parents=True, exist_ok=True)
        draw_comparison_sheet(variants, "day", DAY_SHEET_PATH)
        draw_comparison_sheet(variants, "top", TOP_SHEET_PATH)
        assets["sheets"] = {"day": encode_view(DAY_SHEET_PATH), "top": encode_view(TOP_SHEET_PATH)}
        HTML_PATH.write_text(build_html(assets), encoding="utf-8")
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"Grass-Studienbericht nicht erstellt: {exc}", file=sys.stderr)
        return 1
    print(f"Erstellt: {HTML_PATH}")
    print(f"Erstellt: {DAY_SHEET_PATH}")
    print(f"Erstellt: {TOP_SHEET_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
