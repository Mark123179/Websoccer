"""Dated, source-backed facts; do not replace these with the mixed deliveries."""

CHECKED_AT = "2026-10-27"
REPORT = "docs/import-pilot/schweiz-serien-ohne-sieg-quellenpruefung.md"


def source(name, url):
    return {"name": name, "url": url, "checked_at": CHECKED_AT}


RECORDS = {
    434: {
        "value_numeric": 16,
        "value_display": "16 Pflichtspiele ohne Sieg",
        "period_from": "1942-11-29",
        "period_to": "1943-05-23",
        "season": "1942/43",
        "competition": "Nationalliga / Schweizer Cup",
        "context": (
            "Nachgewiesene Serie: 15 Ligaspiele und die Cup-Niederlage gegen "
            "Locarno am 03.01.1943; fünf Remis, elf Niederlagen. "
            "Begrenzende Siege: 22.11.1942 gegen St. Gallen (2:0), "
            "30.05.1943 in Biel (1:0). Keine alten Intertoto-Spiele. "
            "Die gemischte Lieferung 1981 ergibt ohne Intertoto nur 14; "
            "1965 ergibt 12. Die 15er-Ligaserie 1941/42 wird durch Cupsiege "
            "unterbrochen. Vergleich der verfügbaren TM-Spielhistorie "
            "1933/34–2026/27 mit RSSSF-Cup-Ergänzungen; historische "
            "Quellenlücken sind keine Vollständigkeitsgarantie. "
            f"Spielreihe und Abdeckungsgrenzen: {REPORT}."
        ),
        "sources": [
            source("Transfermarkt, Spielplan 1942/43",
                   "https://www.transfermarkt.de/fc-luzern/spielplan/verein/434/saison_id/1942/plus/1"),
            source("RSSSF, Erik Garin und Peter Kungler, Switzerland 1942/43",
                   "https://www.rsssf.org/tablesz/zwit43.html"),
            source("RSSSF, Switzerland 1941/42 (unterbrechende Cupsiege)",
                   "https://www.rsssf.org/tablesz/zwit42.html"),
            source("RSSSF, Switzerland 1968/69 (Cup-Wiederholungsspiel)",
                   "https://www.rsssf.org/tablesz/zwit69.html"),
            source("RSSSF, Switzerland 1974/75 (zusätzliche Cup-Niederlage)",
                   "https://www.rsssf.org/tablesz/zwit75.html"),
        ],
    },
    321: {
        "value_numeric": 16,
        "value_display": "16 Pflichtspiele ohne Sieg",
        "period_from": "2001-11-24",
        "period_to": "2002-05-04",
        "season": "2001/02",
        "competition": "Nationalliga A / Finalrunde",
        "context": (
            "16 Ligaspiele ohne Sieg: ein Remis, 15 Niederlagen. "
            "Begrenzende Siege: 17.11.2001 bei Servette (3:2), "
            "08.05.2002 gegen Young Boys (3:1). Cup-Aus bereits am "
            "11.11.2001 in Yverdon, also vor Beginn der Serie. "
            "Keine alten Intertoto-Spiele. Die gemischte Lieferung 1978 "
            "ergibt ohne Intertoto 15 und endet am Ligacup-Sieg vom "
            "02.08.1978; sie ist nicht der Ersatzrekord. "
            "Vergleich der verfügbaren TM-Spielhistorie 1955/56–2026/27; "
            "historische Quellenlücken sind keine Vollständigkeitsgarantie. "
            f"Spielreihe und Abdeckungsgrenzen: {REPORT}."
        ),
        "sources": [
            source("Transfermarkt, Spielplan 2001/02",
                   "https://www.transfermarkt.de/fc-sion/spielplan/verein/321/saison_id/2001/plus/1"),
            source("RSSSF, Switzerland 2001/02",
                   "https://www.rsssf.org/tablesz/zwit02.html"),
            source("Transfermarkt, Vergleichsserie 1977/78",
                   "https://www.transfermarkt.de/fc-sion/spielplan/verein/321/saison_id/1977/plus/1"),
            source("Transfermarkt, Ligacup-Sieg 02.08.1978",
                   "https://www.transfermarkt.de/spielbericht/index/spielbericht/3136863"),
        ],
    },
}
