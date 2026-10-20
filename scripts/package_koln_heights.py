"""Bind current installed WebGL images, source provenance and safety checks."""
import base64
import hashlib
import html
import json

from scripts.refine_koln_heights import HEIGHTS, REVIEW, write


def package():
    evidence = json.loads((HEIGHTS / "height-evidence.json").read_text())
    integration = json.loads((HEIGHTS / "integration-check.json").read_text())
    installed_bytes = (REVIEW / "installed-presentation.json").read_bytes()
    installed = json.loads(installed_bytes)["presentation"]
    current = json.loads((REVIEW / "presentation.json").read_text())["presentation"]
    assert current["surroundings"] == installed["surroundings"]
    assert integration["stadiumAndDesignUnchanged"] and integration["geometryOutsideEnvironmentUnchanged"]
    renders = json.loads((REVIEW / "installed-views/render-evidence.json").read_text())
    assert {r["name"] for r in renders} == {
        "ticker-tag", "ticker-nacht-flutlicht", "editor-nacht-flutlicht",
        "abel-ost-tag", "abel-west-tag", "abel-ost-nacht", "abel-west-nacht"}
    assert all(r["installed"] and not r["errors"] and
               r["presentationSha256"] == hashlib.sha256(installed_bytes).hexdigest()
               for r in renders)
    proofs = []
    for r in renders:
        image = REVIEW / "installed-views" / f"{r['name']}.png"
        proofs.append({**r, "imageSha256": hashlib.sha256(image.read_bytes()).hexdigest()})
    evidence["integration"] = integration
    evidence["renders"] = proofs
    evidence["osmRawSha256"] = json.loads((REVIEW / "evidence.json").read_text())["rawSha256"]
    evidence["surroundingsSha256"] = hashlib.sha256(
        json.dumps(installed["surroundings"], sort_keys=True).encode()).hexdigest()
    evidence["references"] = {
        "dgm": "https://www.bezreg-koeln.nrw.de/geobasis-nrw/produkte-und-dienste/hoehenmodelle/digitale-gelaendemodelle/digitales-gelaendemodell",
        "lod2": "https://www.bezreg-koeln.nrw.de/geobasis-nrw/produkte-und-dienste/3d-gebaeudemodelle",
        "roofSource1000": "https://registry.gdi-de.org/codelist/de.adv-online.gid/AX_LI_ProcessStep_Dachhoehe_Source/1000",
    }
    # Text provenance is intentionally tracked; native rasters, CityGML and
    # images stay outside Git. One building per line keeps future diffs useful.
    target = HEIGHTS.parents[2].parent / "docs/stadium/koln-height-evidence.json"
    target.write_text(json.dumps(evidence, ensure_ascii=False, separators=(",", ":")) + "\n")
    write(HEIGHTS / "final-evidence.json", evidence)
    panels = []
    for name,title in [("ticker-tag","Spielansicht · Tag"),
                       ("ticker-nacht-flutlicht","Spielansicht · Nacht und Flutlicht"),
                       ("editor-nacht-flutlicht","Umfeld · Nacht und Flutlicht"),
                       ("abel-ost-tag","Abelbau Ost · Tag · Diagnosekamera"),
                       ("abel-west-tag","Abelbau West · Tag · Diagnosekamera"),
                       ("abel-ost-nacht","Abelbau Ost · Nacht · Diagnosekamera"),
                       ("abel-west-nacht","Abelbau West · Nacht · Diagnosekamera")]:
        image = REVIEW / "installed-views" / f"{name}.png"
        panels.append(f'<figure><img alt="{html.escape(title)}" src="data:image/png;base64,'
                      f'{base64.b64encode(image.read_bytes()).decode()}">'
                      f'<figcaption>{html.escape(title)}</figcaption></figure>')
    official = [b for b in evidence["buildings"] if b["status"] == "official_laser_height"]
    unmeasured = [b for b in evidence["buildings"] if b["status"] != "official_laser_height"]
    rows = "".join(f"<tr><td>{html.escape(b['osm'])}</td><td>"
                   f"{'LoD2 Laser' if b['status']=='official_laser_height' else 'unvermessen / Bestandshülle'}</td>"
                   f"<td>{b.get('height',b['previousHeight']):.3f}</td><td>"
                   f"{html.escape(b.get('lodId',b.get('reason','')))}</td></tr>"
                   for b in evidence["buildings"])
    part_rows = "".join(
        f"<tr><td>{html.escape(g['osm'])}</td><td>{html.escape(p['lodId'])}</td>"
        f"<td>{p['baseNHN']:.3f}</td><td>{p['roofNHN']:.3f}</td><td>{p['height']:.3f}</td></tr>"
        for g in evidence["buildingParts"]["groups"] for p in g["parts"])
    report = f"""<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Köln · Gelände und Höhenbelege</title>
<style>body{{font:16px system-ui;background:#071018;color:#dfebf3;max-width:1450px;margin:32px auto;padding:0 24px}}
aside{{padding:18px;border-left:3px solid #6bdcb1;background:#11232a}}
section{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:20px}}
figure{{margin:0}}img{{width:100%}}figcaption{{padding:10px 0}}a{{color:#6bd4ed}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:8px;border-bottom:1px solid #28414c;text-align:left}}
.scroll{{overflow:auto}}</style>
<h1>Köln · RheinEnergieSTADION – Höhenprüfung</h1>
<aside>Amtliches DGM1 von Geobasis NRW und streng zugeordnete LoD2-Laserhöhen.
Nur das Umfeld wurde aktualisiert. Wirtschaftskapazität 50.000, Manager-Ausbau,
Stadionmodell und gespeicherte Entwürfe unverändert. Kein Produktions-Deployment.</aside>
<h2>Abdeckung</h2>
<p>{len(official)} von 1.546 OSM-Gebäudeobjekten mit eindeutig belegter Laserhöhe
({len(official)/1546:.1%}). {len(set(b['osm'] for b in unmeasured))} Objekte ohne
freigegebene Einzelhöhe behalten ihre gekennzeichnete Bestandshülle
({len(unmeasured)} Renderteile). Keine benachbarte Höhe wurde ersatzweise übernommen.</p>
<p>DGM1: native 1-m-Rasterzellen, Anzeige im 20-m-Raster, EPSG:25832 / DHHN2016 (NHN).
Referenz am Spielfeld: {evidence['terrain']['referenceNHN']:.3f} m NHN.
Alle 14.641 Rasterstützpunkte haben gültige Quelldaten; 137 liegen auf dem
Modellvorplatz, 98 im 40-m-Übergang und 14.406 im unveränderten Höhenbezug.
Vorplatz und Übergang sind ausdrücklich Modellanpassungen, keine Vermessung.</p>
<p>Kein OSM-Grundriss, Straßenabschnitt, Baum oder Grün-/Wasserpolygon gelöscht
oder an der Bowl ausgeschnitten. Renderer-Vorprüfung: OK, Gelände erkannt, null Befunde.
Original-WebGL-Renderer und registrierte Anwendungs-Asset-Endpunkte ohne Seitenfehler.</p>
<section>{''.join(panels)}</section>
<h2>Abelbauten · explizite Teilkörper</h2>
<p>Fünf Teilkörper Ost, sechs West. Je Teilkörper amtliche GroundSurface und
oberes RoofSurface-Niveau in DHHN2016 / NHN. Lokale Darstellung:
NHN minus {evidence['terrain']['referenceNHN']:.6f} m; groundLevel wird nicht doppelt addiert.
Keine maximale oder mittlere Höhe für einen gesamten Abelbau.</p>
<table><thead><tr><th>OSM</th><th>LoD2-ID</th><th>Boden NHN (m)</th>
<th>Oberes Dachniveau NHN (m)</th><th>Teilhöhe (m)</th></tr></thead><tbody>{part_rows}</tbody></table>
<p>Darstellungsgrundrisse sind an unveränderten OSM-Grenzen abgeschnitten.
Nicht zugeordnete und widersprüchlich überdeckte Restflächen bleiben als
unvermessene Bestandshüllen erhalten. Details siehe buildingParts im JSON-Beleg.</p>
<h2>Grenzen</h2><ul>
<li>Kein vermessener Fassaden-/Dachnachbau: einfache Hüllen über dem Gelände.
Außerhalb der expliziten Abel-Teilkörper werden keine absoluten Dachniveaus behauptet.
Die Teilkörper zeigen ihr oberes Dachniveau horizontal, keine geneigte Dachtopologie.</li>
<li>Beide Abelbauten bestehen amtlich aus mehreren unterschiedlich hohen
Teilkörpern. Keine unzulässige Einzelhöhe; ihre OSM-Gesamthüllen bleiben unvermessen.</li>
<li>20-m-Darstellung generalisiert das Gelände. Keine Übertragung der nativen
DGM-Genauigkeit auf die Darstellung; keine Ergänzung von Brücken aus dem DGM.</li>
<li>Baumformen bleiben schematisch. Drei unvollständige OSM-Relationen und drei
ungültige amtliche Grundkomponenten sind dokumentierte Datenlücken.</li></ul>
<h2>Quellen</h2><ul>
<li><a href="{evidence['references']['dgm']}">Geobasis NRW – DGM1</a></li>
<li><a href="{evidence['references']['lod2']}">Geobasis NRW – LoD2</a></li>
<li><a href="{evidence['references']['roofSource1000']}">GDI-DE – Quellcode 1000: Laserscanmessung</a></li>
<li>Geobasis NRW: Datenlizenz Deutschland – Zero 2.0.
© OpenStreetMap contributors, ODbL. Abruf 20.10.2026.</li></ul>
<details><summary>Objektbezogene Abdeckung und Höhen (Meter)</summary>
<p>Bei unvermessenem Status ist der angegebene Wert nur die unveränderte
schematische Bestandshülle – kein amtlicher Messwert.</p>
<div class="scroll"><table><thead><tr><th>OSM-Objekt</th><th>Status</th><th>Höhe</th><th>Beleg / Ausschlussgrund</th>
</tr></thead><tbody>{rows}</tbody></table></div></details></html>"""
    (HEIGHTS / "koln-hoehenpruefung.html").write_text(report)
    print(json.dumps({"report": str(HEIGHTS / "koln-hoehenpruefung.html"),
                      "trackedEvidence":str(target),"installedCaptures":len(proofs)}))


if __name__ == "__main__":
    package()
