# Kalibrierung & Regler-Pflege (Finanzsystem Phase 7)

Spec-Referenz: `attached_assets/SPEC_Finanzsystem_1784457895034.md`, Kap. 16
(Kalibrierungs-Checkliste) und Kap. 17 (Regler-Übersicht). Grundsatz:
**Formeln sind spec-fixiert — justiert werden ausschließlich Reglerwerte in
der `EconomyParameter`-Tabelle, nie Code-Konstanten. Keine Selbstjustierung:
jede Anpassung ist eine bewusste Admin-Entscheidung.**

## Werkzeuge

| Werkzeug | Zweck |
| --- | --- |
| Creator → **Kalibrierung** (`/creator/kalibrierung/`) | Kennzahlen-Report, Regler-Übersicht mit `[KALIBRIERUNG]`-Badge, Saison-Historie, Edit-Formulare, Leitfaden |
| `python manage.py kalibrierungs_report [--saison N] [--json]` | derselbe Report als Command (für Doku/Automation) |
| Modul `game/economy/kalibrierung.py` | Kennzahlen-Aggregationen + Regler-Registry (Single Source) |

## Kennzahlen & Zielkorridore (Kap. 16)

| Kennzahl | Zielkorridor | Alarm | zuständige Regler |
| --- | --- | --- | --- |
| Geldmengenwachstum/Saison | ≈ MW-Drift ± 2 pp | > 4 %/Saison | `BETRIEBSQUOTE` (wichtigster Regler), `TV_TOEPFE`, `SPONSOR_MW_ANTEIL`, Auktionsvolumen (Admin-Empfehlung ohne Key) |
| Ablöse/MW-Median | 1,3 – 1,8 | > 2,2 | `KI_ANGEBOTS_KADENZ`, `KI_KAEUFER`, `SCHMERZGRENZE_KONSTANTEN` |
| Gehaltslasten (klein / top) | 16–20 % / 28–30 % des Kader-MW | > 10 pp außerhalb | `GEHALT_BASIS`, `GEHALT_PROGRESSION` |
| Zuschauer-Plausibilität | Zuschauer ÷ Basisnachfrage 0,5–1,3 | — (nur ok/warn) | `NACHFRAGE_KOEFF`, `NACHFRAGE_EXP`, `PREIS_ELASTIZITAET` |
| KI-Kaufvolumen-Anteil | ≤ Governor-Limit (50 %) | Limit überschritten | `KI_ANGEBOTS_KADENZ`, `KI_KAEUFER` |

Status-Semantik: `ok` (im Korridor) · `warn` (außerhalb, unter Alarmschwelle)
· `alarm` (Schwelle gerissen) · `nicht_messbar` (Datenbasis reicht nicht —
bewusst **nie** stilles `ok`).

## Saison-Versionierung

Speichern in der Regler-Übersicht schreibt immer eine Zeile
`(saison=aktuelle Saison, key)` per `update_or_create` — ältere Saisons
bleiben unangetastet (Snapshot-Semantik, `get_param` fällt auf die jüngste
frühere Saison zurück). Schutzmechanismen im Edit-Formular:

- **JSON-Typ-Validierung**: der Top-Level-Typ (Zahl/Text/Objekt/Liste/Bool)
  muss dem bisherigen Wert entsprechen — Typwechsel würden Finanzläufe brechen.
- **`KI_KAEUFER.dry_run` wird bewahrt**: der operative Schalter der
  KI-Transferzentrale wird beim Speichern aus dem Altwert übernommen, damit
  ein Regler-Edit die KI nicht versehentlich scharf schaltet oder lahmlegt.
- **Keine neuen Keys über die UI** — Keys entstehen nur über Seed-Migrationen.

## Erst-Kalibrierungslauf (19.07.2026, Saison 0)

```
Kalibrierungs-Report — Saison 0 (Spec Kap. 16)
Status: 0 Alarm · 0 außerhalb Korridor · 3 nicht messbar

[NICHT MESSBAR] Geldmengenwachstum vs. MW-Drift
    Ist: Wachstum +1,9 % · MW-Drift —
    → MW-Drift braucht zwei Saison-Snapshots (erst ab Saison 1 messbar).
[NICHT MESSBAR] Ablöse/MW-Median
    Ist: Median — (0 Transfers)
    → Keine Transfers mit MW-Bezug in Saison 0.
[NICHT MESSBAR] Gehaltslasten nach Vereinsgröße
    Ist: klein 0,5 % · top 0,7 % (18 Vereine) — anteilig, laufende Saison
    → Korridorvergleich erst nach Saisonabschluss.
[IM KORRIDOR] Zuschauer-Plausibilität
    Ist: Median-Ratio 0,81 · Auslastung 68,6 % (9 Heimspiele)
    Ausreißer: Borussia Mönchengladbach — Ratio 1,30 (Bandobergrenze)
[IM KORRIDOR] KI-Kaufvolumen-Anteil
    Ist: 0 % von 42.500.000 € Transfervolumen (Limit 50 %)
```

### Abweichungsanalyse & Entscheidung

- **Keine Regler-Anpassung in Saison 0.** Begründung: Die beiden messbaren
  Kennzahlen (Zuschauer, KI-Anteil) liegen im Korridor. Die drei übrigen sind
  strukturbedingt nicht messbar — Saison 0 ist die erste Ledger-Saison
  (kein zweiter MW-Snapshot), es gab noch keine MW-relevanten Transfers, und
  Gehälter sind erst anteilig gebucht. Eine Justierung auf dieser Datenbasis
  wäre Rauschen, kein Signal.
- Das absolute Geldmengenwachstum (+1,9 %) liegt nachrichtlich unter der
  4-%-Alarmschwelle — `BETRIEBSQUOTE` bleibt unverändert.
- Der einzelne Zuschauer-Ausreißer (Gladbach, Ratio exakt 1,30) liegt auf der
  Bandkante und ist mit 1 von 9 Spielen kein Muster.

### Wiederholungs-Workflow (jede Saison nach Abschluss)

1. `python manage.py kalibrierungs_report --saison <abgeschlossene Saison>`
2. Abweichungen (`warn`/`alarm`) je Kennzahl über den im Report genannten
   Regler in Creator → Kalibrierung anpassen (kleine Schritte, ein Regler
   pro Saison, Wirkung erst in der Folgesaison bewerten).
3. Bei Geldmengen-Alarm zusätzlich prüfen: Auktionsvolumen erhöhen
   (zweite große Geldsenke, bewusste Admin-Aufgabe ohne Parameter-Key).
