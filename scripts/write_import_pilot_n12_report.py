"""Generate the N12 delivery from completed verification artifacts only."""
import base64
import csv
import hashlib
import html
import json
import re
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/import-pilot"


def inline(text):
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)


def render_markdown(text):
    lines, output, index = text.splitlines(), [], 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("|"):
            table = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                    tag = "th" if not table else "td"
                    table.append("<tr>" + "".join(f"<{tag}>{inline(cell)}</{tag}>" for cell in cells) + "</tr>")
                index += 1
            output.append('<div class="table-wrap"><table>' + "".join(table) + "</table></div>")
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            output.append(f"<h{level}>{inline(line[level:].strip())}</h{level}>")
        elif line.startswith("- "):
            output.append("<p class='bullet'>• " + inline(line[2:]) + "</p>")
        elif line.strip():
            output.append("<p>" + inline(line) + "</p>")
        index += 1
    return "\n".join(output)


def generate():
    log = Path("/tmp/n12-full-final.log").read_text()
    match = re.search(r"^Ran (\d+) tests in ([\d.]+)s$", log, re.M)
    assert match and re.search(r"^OK$", log, re.M), "Completed green full suite required."
    assert not re.search(r"^(FAILED|FAIL:|ERROR:)", log, re.M)
    assert "N12_V3_EVIDENCE=" in log
    display_log = Path("/tmp/n12-display-final.log").read_text()
    assert re.search(r"^Ran 9 tests in [\d.]+s$", display_log, re.M)
    assert re.search(r"^OK$", display_log, re.M)
    assert not Path("/tmp/n12-browser-session.json").exists(), "Temporary session must be removed."
    browser = json.loads((OUT / "n12-browser-verification.json").read_text())
    assert browser["final"]["verdict"] == "success"
    before = json.loads((OUT / "n12-before.json").read_text())
    after = json.loads((OUT / "n12-after.json").read_text())
    repair = json.loads((OUT / "n12-context-repair.json").read_text())
    diff = json.loads((OUT / "n12-v3-diff.json").read_text())
    assert after["changed_tables"] == ["game_clubrecord"]
    assert after["pilot"]["package_hashes"][-1] == diff["v2"]
    screenshots = sorted((OUT / "n12-screenshots").glob("[0-9][0-9]-*.png"))
    assert len(screenshots) == 9, "Nine actual-pilot captures required."
    csv_path = OUT / "n12-staerken-51.csv"
    csv_rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig"), delimiter=";"))
    assert len(csv_rows) == 51
    changed = [
        ("1", "views_management.py", "Titel aus Kategorie-Einzeleinträgen; vorhandene SIM-Titel zusätzlich, ohne Doppelzählung."),
        ("2", "views_management.py", "Trainerplatz 7 zeigt longest_win_streak_coach; Antragsauswahl verwendet denselben Schlüssel."),
        ("3, 4", "views_management.py", "Reale Saison unverändert; Datum/Zeitraum mit Jahr. SIM-Format Saison #4 bleibt bestehen."),
        ("5", "player_detail.html", "Gespeicherter Ablösetext einschließlich Leih-Ende und Leihgebühr statt festem Leihe."),
        ("6", "club_import/presentation.py; views.py", "Gleicher Tag: Reihenfolge aus Originalpaket; Ramaj-Leihe vor Kauf am 03.02.2025."),
        ("7, 8", "club_detail.html", "Gründungsjahr 1909; leere Tertiärfarbe ausgeblendet."),
        ("9", "club_profile.py; club_profile_highlights.py; identity_card.html; club_detail.html", "Profis nach erster Mannschaft: 28, Ø24,4. U21-Alter, Highlights und Jugendlink nur Creator."),
        ("10", "presentation.py; views.py; player_detail.html; squad_page.html; _loan_card.html", "Besitzer/Partner-Originalnamen, echtes Beginn-Datum, bis Ende Saison 1; keine Anzeige loan_until."),
        ("11", "templatetags/package_display.py; player_detail.html", "Deutsche Tausenderpunkte bei Kopf-Marktwert, Verlauf und Gehalt."),
        ("12", "package_display.py; package_hub.html; halloffame.html; package_preview.html", "Deutsche Kategorien, Offen/Einzelsperre und Antragsgruppen. Quellschlüssel unverändert."),
        ("13", "views_management.py", "Einheit wird nicht wiederholt, auch wenn sie innerhalb des Original-Werttextes steht."),
        ("14", "player_detail.html", "Startwert-Punkt ohne Vereinszeile; Spielstartwert bleibt gekennzeichnet."),
        ("15", "club_profile_highlights.py", "Nicht belegte Passquote/Note: Gedankenstrich statt erfundener Werte."),
        ("N55", "models.py; migrations/0191_clubrecord_context_text.py; package_service.py", "Meiste Titel: nur Zahl/Halter, Beleg erhalten; Kontext ohne 200-Zeichen-Kürzung."),
        ("N56/N60", "package_validation.py; package_service.py; package_preview.py; package_preview.html", "super_cup gültig; sechs Kategorieänderungen sichtbar. Keine Duplikate; Kategorie-Upload resavet keine anderen Fakten; Stale-Preview-Guard umfasst Titel."),
        ("Navigation", "halloffame.html; views_management.py; home.html; player_detail.html; N11-Bericht", "Verein bleibt bei Raum, Pfeilen, Modus, Abbrechen und Formular; URL-Namen berücksichtigen Pilot-Präfix; Bericht club=8."),
    ]
    links = [
        ("home.html", "2× /clubs/ (Vereinsauswahl/Transfermarkt)", "club_list"),
        ("home.html", "/clubs/{{ primary_club.id }}/", "club_detail"),
        ("home.html", "/players/{{ spotlight.player_id }}/", "player_detail"),
        ("home.html", "4× /clubs/{{ next/last_match_home/away_club.id }}/", "club_detail"),
        ("home.html", "/players/{{ row.player.id }}/", "player_detail"),
        ("home.html", "/liga/2/", "league_detail"),
        ("home.html", "/clubs/{{ item.club_id }}/ und 2× /clubs/ (Nachrichten/Live)", "club_detail / club_list"),
        ("player_detail.html", "/clubs/{{ player.club.id }}/", "club_detail"),
        ("Nachtrag-11-Bericht", "/import-pilot/management/halloffame/?club=1", "club=8, Markdown und HTML"),
    ]
    sections = [
        "# Import-Pilot: Bericht zu Nachtrag 12",
        "Stand: 06.10.2026. Umfang: N54–N61. **Halt zur Gegenprüfung durch Claude. Kein Import des Supercup-Korrekturpakets in den echten Pilot.**",
        "## 1. Gesamtlauf",
        f"- `python manage.py test game.tests --verbosity=0 --keepdb`: **{match[1]} Tests, OK**, {match[2]} Sekunden.",
        "- Gegenüber dem vorigen vollständigen Lauf: neun zusätzliche Nachtrag-12-Tests. Der bestehende SIM-Saison-ohne-Jahr-Test bleibt grün.",
        "- Nach der abschließenden, ausschließlich paketbezogenen Umbruch-/Schriftkorrektur: alle neun Anzeige-Tests erneut grün; kein weiterer Backend-Code verändert.",
        "- Zusätzlich geprüft: Django-Systemcheck, migrationsfreie Modellkonsistenz, Diff-Whitespace; zwei neu gestartete Webdienste laufen.",
        "- Vollständiges Protokoll: `n12-full-suite.log`. Die absichtlich provozierten Fehlerpfad-Tracebacks sind Testfälle, keine fehlgeschlagenen Tests.",
        "## 2. Ansichten und Vorlagen je Punkt",
        "| Punkt | Dateien unter game/ | Änderung |", "|---|---|---|",
        *[f"| {point} | `{files}` | {description} |" for point, files, description in changed],
        "## 3. Echter Pilot: unverändert v2",
        f"- Aktiver Paket-Hash: `{diff['v2']}`.",
        "- Arbeitsliste: **156 Zeilen / 128 offen / 28 durch Paket erledigt**. **49 Stärken, zwei Einzelsperren**. Keine zusätzliche Sperre oder neu erzeugte Vereinsreferenz.",
        "- Die echten Pilot-Kacheln zeigen aktuell **8 / 11 / 3**: v2 enthält elf national_cup-Einträge. Das ist kein Namensfehler und wird nicht vorweg manipuliert.",
        "- **8 / 5 / 3** ist nach dem getrennt getesteten Kategorie-Upload korrekt. Sechs Supercup-Titel bleiben in Titelliste und Trophäenschrank, zählen aber nicht in den drei Kacheln.",
        "- BVB-ID ist 8. Keine Managerzuweisung oder sonstige Kontoänderung für die Fotos. Nur eine befristete technische Browser-Sitzung wurde verwendet und anschließend entfernt.",
        "## 4. Alle 51 Spieler",
        "- Datei: `n12-staerken-51.csv`, UTF-8 mit BOM, Semikolon für Tabellenprogramme.",
        "- Enthält Name, TM-/FMInside-/CMTracker-ID mit Status, ID-Prüfdatum und Quellen-Sperre, beide Quell-Ratings/Potenziale, FMInside-Spanne, gemeinsame Rohbasis und Rohpotenzial 0–200, Einzelsperre und Grund.",
        "- 51 Zeilen; 49 mit beiden berechenbaren Rohwerten, zwei gesperrt. Fehlende Quellen bleiben leer, keine Stärke wird erfunden. Export verwendet ausschließlich die unveränderten reinen Rechenfunktionen, keine persistierende Neuberechnung.",
        f"- CSV-SHA256: `{hashlib.sha256(csv_path.read_bytes()).hexdigest()}`.",
        "| Stichprobe | Basis | Potenzial |", "|---|---:|---:|",
    ]
    for name in ("Ethan Nwaneri", "Samuele Inácio", "Luca Reggiani", "Luke Fahrenhorst", "Bennedikt Wüstenhagen"):
        row = next(row for row in csv_rows if row["Name"] == name)
        sections.append(f'| {name} | {row["Basis Rohskala 0–200"]} | {row["Potenzial Rohskala 0–200"]} |')
    sections += [
        "## 5. Fingerprints und einzige autorisierte Datenänderung",
        f"- Vorher/nachher: **{len(before['tables'])} Game-Fachtabellen**. **143 identisch**, ausschließlich game_clubrecord anders.",
        f"- Rekord `{repair['key']}`, interne ID {repair['record_id']}: context_line **200 → 233 Zeichen**, direkt aus gespeichertem Originalpaket.",
        "- Zeilenvergleich vor/nachher bestätigt: ausschließlich context_line verändert. updated_at identisch; keine anderen Rekordfelder, Paketzeilen, Spieler, Werte, Transfers, Stärken oder Arbeitslistentexte verändert.",
        f"- game_clubrecord: jeweils 24 Zeilen; MD5 vorher `{before['tables']['game_clubrecord']['md5']}`, nachher `{after['pilot']['tables']['game_clubrecord']['md5']}`.",
        "- Maschinenbelege: `n12-before.json`, `n12-after.json`, `n12-context-repair.json`. Tabellenhashes enthalten vollständige Zeilen inklusive IDs und Zeitstempeln; keine Rohdaten der Konten exportiert.",
        "- Der aktive Altbestand wurde ebenfalls lesend erfasst: `n12-public-before.json` / `n12-public-after.json`. Migrationseintrag/-Sequenz erwartbar geändert; sämtliche Rechte-/Rollen-/Constraint-Metadaten identisch. Zusätzlich weicht der Managerprofil-Hash während laufender Hauptapp-Aktivität ab. Aus dem aggregierten Vorher-Hash allein lässt sich keine einzelne Spalte zuordnen; keine falsche Behauptung vollständiger Bytegleichheit. Dieser Altbestand-Unterschied betrifft nicht den getrennten Pilot.",
        "## 6. Migration",
        "- `game.0191_clubrecord_context_text`: context_line von CharField(200) zu TextField.",
        "- In Hauptschema und Pilot angewendet, unabhängig vom Verhaltensschalter. Kein Daten-Reset, keine Rückmigration; alte Migrationen unverändert.",
        "## 7. Ersetzte feste Links",
        "| Datei | Vorher | URL-Name / Korrektur |", "|---|---|---|",
        *[f"| `{file}` | `{old}` | `{new}` |" for file, old, new in links],
        "## 8. Getrennter Testbestand: v2 → v3",
        f"- SHA256 von v3-data.json korrekt: `{diff['v3']}`. Vollvergleich bestätigt **genau sechs geänderte Werte**, ausschließlich competition.category. Manifest: nur data_sha256.",
        "| Wettbewerb | Saison | Vorher | Nachher |", "|---|---|---|",
        *[f'| {row["competition"]} | {row["season"]} | {row["before"]} | {row["after"]} |'
          for row in diff["changed_data_values"]],
        "- Unit-Test: Vorschau schreibfrei, genau sechs Titeländerungen, null sonstige angezeigte Änderungen; Arbeitsliste 0 neu / 128 weiterhin offen / 0 erledigt / 0 wieder offen.",
        "- Nach Testimport: 30 Titel, davon fünf national_cup und sechs super_cup. Derselbe Titel behält seine Zeilen-ID; kein doppelter Titel.",
        "- Vollständige Game-Tabellenhashes vor/nachher unterscheiden sich nur bei SourceImportRun (neues Archiv), sechs ClubTrophyEntry-Kategorien und abgeleitetem ClubTrophy-Cache. **Spieler, Marktwertpunkte, Transfers, Rekorde, Stärken und Arbeitsliste vollständig identisch**.",
        "- Erneute Bestätigung desselben Pakets: unverändert, keine Schreiboperation. Gleichzeitige Titeländerung verändert den Vorschau-Guard. Vorhandene SIM-Titel werden zusätzlich und ohne doppelte Zählung berücksichtigt.",
        "- Belege: `n12-v3-diff.json`, `game/tests/test_package_display.py`, N12_V3_EVIDENCE im Gesamtlauf.",
        "## 9. Bildschirmfotos aus dem echten Pilot",
        "- Neun vollständige Seitenfotos unter `n12-screenshots/`, zusätzlich als `n12-screenshots.zip`. Im HTML-Bericht direkt eingebettet.",
        "- Nach Browserbefund wurden ausschließlich die zwei Paketvorlagen lesbarer gemacht: Plakettentexte kleiner/mehrzeilig, Halternamen ohne Ellipse; breitere Transferkarte, Gebühren in eigener Zeile und vollständige Liste scrollbar; Marktwert-Quellzeilen ohne überlappende Spalten. Fotos 03–09 danach erneuert, Vereins-/Kaderfotos unverändert gültig.",
        "- Browser-Nachprüfung erfolgreich: geforderte Werte vollständig lesbar, keine Nachbarüberlagerung. Einzelne lange Wörter brechen in den schmalen Plaketten weiterhin mitten im Wort um; 2–3 Pixel rechnerischer Textüberhang ohne abgeschnittenen Pflichtwert bleiben als kleine typografische Einschränkung dokumentiert.",
        *[f"- `{path.name}`" for path in screenshots],
        "## 10. Abgrenzung und Halt",
        "- Punkt 16 (Bilder/Flaggen/Wappen) bleibt zur Prüfung auf dem Live-Server. Fehlende lokale Bilder werden nicht ergänzt und sind kein Abnahmebeleg für Live.",
        "- Vereinswert-Regel und Stärkeformel unverändert. Jüngster Spieler bleibt gespeichert, nicht angezeigt. Alle sechs Startwerte bleiben 50.000 €, 05.10.2026, Gehalt 250 €.",
        "- Kein Supercup-Paketimport in den Pilot, kein Reset/T5, keine Dortmund-Szenensicherung, keine Hetzner-Änderung und keine Veröffentlichung.",
        "- **Hier ist der vereinbarte Halt.** Zuerst Claude-Gegenprüfung; anschließend erst die freigegebene v2-Sicherung und der Upload mit Bestätigung durch Mark.",
    ]
    text = "\n\n".join(
        "\n".join(group) if isinstance(group, list) else group for group in sections)
    # Keep adjacent table rows together for Markdown and the HTML renderer.
    text = re.sub(r"\n\n(?=\|)", "\n", text)
    text = re.sub(r"(?<=\|)\n\n(?=\|)", "\n", text)
    (OUT / "nachtrag12-bericht.md").write_text(text + "\n")
    (OUT / "n12-full-suite.log").write_text(log)
    (OUT / "n12-display-tests.log").write_text(display_log)
    (OUT / "n12-tests.json").write_text(json.dumps(
        dict(tests=int(match[1]), seconds=float(match[2]), result="OK",
             display_tests_after_css=9, display_result_after_css="OK",
             command="python manage.py test game.tests --verbosity=0 --keepdb",
             sha256=hashlib.sha256(log.encode()).hexdigest()), indent=2) + "\n")
    figures = []
    for path in screenshots:
        uri = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
        figures.append(f'<figure><img src="{uri}" alt="{html.escape(path.stem)}"><figcaption>{html.escape(path.name)}</figcaption></figure>')
    page = '<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nachtrag 12 · Import-Pilot</title><style>body{margin:0;color:#23313b;background:#f4f6f7;font:16px/1.6 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:40px 24px}h1{font-size:34px}h2{margin-top:42px;border-top:1px solid #ccd5dc;padding-top:24px}code{font-size:13px;overflow-wrap:anywhere}strong{color:#133d4c}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;margin:16px 0}td,th{padding:10px;text-align:left;border:1px solid #ced8dd;vertical-align:top}th{background:#dfe9ec}.bullet{margin:.4em 0}figure{margin:24px 0;background:white;padding:12px}img{width:100%;height:auto}figcaption{font-size:13px;color:#596b77}@media print{body{background:white}main{padding:0}figure{break-inside:avoid}}</style><main>'
    page += render_markdown(text) + "<h2>Fotobelege</h2>" + "".join(figures) + "</main></html>"
    (OUT / "nachtrag12-bericht.html").write_text(page)
    with zipfile.ZipFile(OUT / "n12-screenshots.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in screenshots:
            archive.write(path, path.name)
    # Regenerate the sole incorrect URL in the old generated report, preserving
    # its complete body and embedded image bytes.
    old_path = OUT / "nachtrag11-bericht.html"
    old = old_path.read_text()
    wrong = "/import-pilot/management/halloffame/?club=1"
    assert old.count(wrong) == 1
    old_path.write_text(old.replace(wrong, "/import-pilot/management/halloffame/?club=8"))
    print(json.dumps(dict(tests=int(match[1]), screenshots=len(screenshots), csv_rows=len(csv_rows),
                         pilot="v2", changed_tables=after["changed_tables"]), ensure_ascii=False))


if __name__ == "__main__":
    generate()
