---
name: Per-Halbzeit Linien-Delta Design
description: Exploit-Schutz für Mittelfeld + Angriff Halbzeit-Dropdowns; separate line_* Variablen mit einseitigem Cap.
---

# Per-Halbzeit Linien-Delta Design

## Regel

Halbzeit-Dropdowns Mittelfeld und Angriff schreiben in **separate** `line_*`-Variablen (nicht direkt in `s["..."]`):

```python
line_xg_for = line_xg_ag = line_shots = line_risk = line_fatigue = line_poss = 0.0
# ... Midfield-Block ...
# ... Attack-Block ...
line_xg_for = min(line_xg_for, 0.06)   # Vorteil gekappt
line_shots  = min(line_shots,  0.08)   # Vorteil gekappt
# risk / fatigue: KEIN Cap — stapeln sich vollständig
s["xg_for_delta"] += line_xg_for
# ... etc.
```

**Why:** Verhindert Exploit durch Stacking aller drei Linien-Dropdowns auf Maximum (sonst shots ×1.12 erreichbar). Gleichzeitig bleibt die Bestrafung (Risiko, Frische) voll erhalten — Manager der alles nach vorne stellt, soll leiden.

**How to apply:**
- Spielaufbau, Pressing, Matchpläne kommen NACH dem line_*-Block — deren Effekte sind davon unberührt.
- Defense-Dropdown (`hd`) hat eigene strukturelle Effekte (pressing_index, defense_delta, attack_delta) die direkt in `s["..."]` gehen — kein line_*-Wrapper nötig.
- Kohärenz-Penalty: `tief_stehen + offensiv_besetzen + strafraum_besetzen` → `coherence -= 0.04`. Umgekehrt: `hoeher_stehen + offensiv + strafraum` ist KOHÄRENT (kein Penalty).

## Aktuelle Optionen & Werte (Mittelfeld)

| Option | xG für | xG gegen | Poss | Shots | Risk | Fatigue |
|---|---|---|---|---|---|---|
| absichern | −0.015 | −0.030 | −0.005 | −0.020 | −0.04 | −0.010 |
| ballbesitz_sichern | −0.005 | −0.015 | +0.015 | −0.030 | −0.02 | 0 |
| nachruecken | +0.020 | +0.012 | +0.003 | +0.030 | +0.03 | +0.020 |
| offensiv_besetzen | +0.030 | +0.025 | −0.003 | +0.050 | +0.05 | +0.040 |

## Aktuelle Optionen & Werte (Angriff)

| Option | xG für | xG gegen | Poss | Shots | Risk | Fatigue |
|---|---|---|---|---|---|---|
| unterstuetzen | −0.015 | −0.015 | +0.008 | −0.040 | −0.03 | −0.010 |
| abwehrkette_binden | +0.015 | +0.010 | −0.003 | +0.010 | +0.02 | +0.010 |
| strafraum_besetzen | +0.030 | +0.025 | −0.005 | +0.040 | +0.05 | +0.030 |
