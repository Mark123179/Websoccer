# Websoccer – Spezifikation Spielstärke-System

Stand: 2026-06-09  
Version: 2.0  
Ziel: Dieses Dokument beschreibt das finale Stärke-, Potential-, Attribut-, Frische-, Form- und Verletzungssystem für den Websoccer-Manager. Es dient als Implementierungsgrundlage für Replit/Django/Supabase.

---

## 1. Grundidee

Jeder Spieler besitzt eine sichtbare Grundqualität und ein Potential. Im Spiel wird nicht immer nur die feste Basisstärke genutzt. Stattdessen wird pro Match eine Tagesbasis zwischen Basisstärke und Potential gezogen.

Dadurch entsteht ein wichtiges Manager-Prinzip:

- Spieler mit hoher Basisstärke sind verlässlicher.
- Spieler mit großem Potential-Gap können stärker ausschlagen, sind aber unkonstanter.
- Junge Spieler können an guten Tagen überragend sein und an schwachen Tagen deutlich abfallen.
- Der Trainer muss entscheiden: sichere Qualität oder höheres Risiko mit mehr Potential.

---

## 2. Die 6 Schichten der Spielstärke

Die finale Spielstärke eines Spielers entsteht aus sechs Schichten:

```txt
1. Basisstärke aus FMI + SoFIFA/EA
2. Potential-Roll pro Spiel
3. Positionsprofil aus Attributen
4. Positions-Fit
5. Frische-Fit
6. RL-Form-Fit
```

Gesamtformel:

```txt
base_strength_200 = fmi_rating + sofifa_rating
potential_200 = fmi_potential + sofifa_potential
potential_200 = max(potential_200, base_strength_200)

match_base_strength = random_integer(base_strength_200, potential_200)

position_profile_100 = weighted_average(relevant_attributes_for_played_position)
position_profile_200 = position_profile_100 * 2

pre_fit_strength =
    match_base_strength * 0.80
  + position_profile_200 * 0.20

final_match_strength =
    pre_fit_strength
  * position_fit
  * freshness_fit
  * rl_form_fit

final_match_strength = clamp(round(final_match_strength), 1, 200)
```

Wichtig: Die Tagesbasis wird pro Spieler und Match nur einmal gezogen und gespeichert. Sie darf nicht bei jedem Reload neu berechnet werden.

---

## 3. Source-Daten

Im Source-Tab werden nur Rohdaten gespeichert. Diese Werte sind noch nicht die fertigen Websoccer-Werte.

Quellen:

```txt
FMI / FMInside
SoFIFA / EA
Transfermarkt optional als Stammdaten-/Marktwertquelle
```

FMI und SoFIFA liefern Rating, Potential und Attribute bereits auf einer Skala von ungefähr 0–99 beziehungsweise 0–100. Daher erfolgt keine Umrechnung auf 0–100.

---

## 4. Null-Handling bei Quellenwerten

Leere Felder bedeuten: Die Quelle liefert dieses Attribut nicht.

Regeln:

```txt
beide Quellen vorhanden -> Durchschnitt bilden
eine Quelle vorhanden   -> vorhandenen Wert nehmen
keine Quelle vorhanden  -> null / nicht berechenbar
```

Beispiel:

```txt
FMI Technik: 90
SoFIFA Technik: null

combined_technique = 90
```

Falsch wäre:

```txt
(90 + 0) / 2 = 45
```

Null-Werte dürfen niemals als 0 in Durchschnittsberechnungen eingehen.

---

## 5. Basisstärke

Die Basisstärke ist die sichere Grundqualität eines Spielers vor allen Match-Faktoren.

```txt
base_strength_200 = fmi_rating + sofifa_rating
```

Beispiel Michael Olise:

```txt
FMI Rating: 88
SoFIFA Rating: 89

base_strength_200 = 177
```

Skala:

```txt
Minimum: 0
Maximum: 200
```

---

## 6. Potential

Potential ist die mögliche Tagesobergrenze vor den Fits.

```txt
potential_200 = fmi_potential + sofifa_potential
potential_200 = max(potential_200, base_strength_200)
```

Beispiel Michael Olise:

```txt
FMI Potential: 93
SoFIFA Potential: 91

potential_200 = 184
```

Das Potential-Gap ist zugleich ein Konstanz-Indikator:

```txt
gap = potential_200 - base_strength_200
```

Beispiele:

| Spielertyp | Basis | Potential | Gap | Bedeutung |
|---|---:|---:|---:|---|
| erfahrener Star | 180 | 186 | 6 | sehr konstant |
| stabiler Stammspieler | 150 | 160 | 10 | zuverlässig |
| Talent | 130 | 170 | 40 | stark schwankend |
| Rohdiamant | 105 | 170 | 65 | sehr unberechenbar |

---

## 7. Dynamisches Potential aus FMI

Falls FMI ein dynamisches Potential oder eine Range liefert, wird daraus einmalig ein fester FMI-Potentialwert erzeugt.

Regel:

```txt
Beim Import oder Seed einmalig einen Wert innerhalb der Range bestimmen.
Diesen Wert speichern.
Nicht pro Spiel neu auswürfeln.
```

Empfehlung:

```txt
resolved_fmi_potential = seeded_random(range_min, range_max, player_id)
```

Dadurch bleibt der Spieler über die Datenbank hinweg stabil, aber individuelle Talente unterscheiden sich.

---

## 8. Potential-Roll pro Match

Für jedes Match wird eine Tagesbasis zwischen Basisstärke und Potential gezogen.

```txt
match_base_strength = random_integer(base_strength_200, potential_200)
```

Beispiel:

```txt
Basis: 130
Potential: 170

Mögliche Tagesbasis: 130 bis 170
```

Bei 41 möglichen Ganzzahlwerten gilt ungefähr:

| Ereignis | Chance |
|---|---:|
| mindestens 140 | ca. 75,6 % |
| mindestens 150 | ca. 51,2 % |
| über 150 | ca. 48,8 % |
| mindestens 160 | ca. 26,8 % |
| mindestens 165 | ca. 14,6 % |
| exakt 170 | ca. 2,4 % |

Das ist beabsichtigt. Ein Talent bringt sein Potential nicht immer vollständig auf den Platz, kann aber regelmäßig deutlich über seiner Basis spielen.

Wichtig für die Implementierung:

```txt
Der gezogene Wert muss pro Spieler und Match gespeichert werden.
Bei Reloads oder erneuter Anzeige darf kein neuer Wert entstehen.
```

Geeignete Felder:

```txt
match_id
player_id
base_strength_200
potential_200
match_base_strength
pre_fit_strength
final_match_strength
```

---

## 9. Die 13 Feldspieler-Attribute

Die finalen 13 Feldspieler-Attribute sind:

```txt
1. Tempo
2. Ausdauer
3. Kraft
4. Technik
5. Dribbling
6. Passspiel
7. Flanken
8. Abschluss
9. Kopfball
10. Zweikampf
11. Defensivstellung
12. Übersicht
13. Teamwork
```

Die Werte bleiben auf 0–100.

Wenn beide Quellen Werte liefern:

```txt
combined_attribute = round((fmi_attribute + sofifa_attribute) / 2)
```

Wenn nur eine Quelle einen Wert liefert:

```txt
combined_attribute = available_source_value
```

---

## 10. Attribut-Mapping

Mögliche Mapping-Logik:

| Websoccer | FMI | SoFIFA/EA |
|---|---|---|
| Tempo | Pace / Acceleration | Pace / Acceleration / Sprint Speed |
| Ausdauer | Stamina | Stamina |
| Kraft | Strength | Strength |
| Technik | Technique / First Touch | Ball Control / Reactions / Composure |
| Dribbling | Dribbling | Dribbling |
| Passspiel | Passing | Short Passing / Long Passing |
| Flanken | Crossing | Crossing |
| Abschluss | Finishing | Finishing / Shooting |
| Kopfball | Heading | Heading Accuracy |
| Zweikampf | Tackling | Standing Tackle / Sliding Tackle |
| Defensivstellung | Marking / Positioning defensiv | Defensive Awareness / Interceptions |
| Übersicht | Vision / Decisions | Vision |
| Teamwork | Teamwork / Work Rate / Decisions | Work Rate / Composure / Reactions / Aggression, falls sinnvoll |

Wichtig bei Defensivstellung:

SoFIFA hat offensive Positionierung und defensive Awareness. Für `Defensivstellung` darf nicht versehentlich offensive Positionierung verwendet werden. Bei großen Abweichungen zwischen FMI und SoFIFA sollte eine Warnung angezeigt werden.

---

## 11. Source-Warnungen bei Datenabweichung

Wenn FMI und SoFIFA bei einem Attribut stark voneinander abweichen, soll die UI das markieren.

Regel:

```txt
Differenz 0–15  -> normal
Differenz 16–30 -> gelbe Warnung
Differenz >30   -> rote Warnung: Mapping prüfen
```

Beispiel:

```txt
FMI Defensivstellung: 40
SoFIFA Defensivstellung: 86
Differenz: 46

=> rote Warnung
```

Das schützt vor fehlerhaftem Mapping.

---

## 12. Standards

Standards werden separat gespeichert und nicht direkt in die Basisstärke eingerechnet.

```txt
Ecken
Freistoß
Elfmeter
```

Regeln:

```txt
Elfmeter: Durchschnitt aus FMI Penalty Taken und SoFIFA/EA Penalties, falls beide vorhanden
Freistoß: Durchschnitt aus FMI Free Kick Taking und SoFIFA/EA FK Accuracy, falls beide vorhanden
Ecken: meistens FMI Corners, wenn SoFIFA keinen passenden Wert liefert
```

Null-Handling wie bei Attributen:

```txt
beide Quellen vorhanden -> Durchschnitt
eine Quelle vorhanden   -> vorhandenen Wert
keine Quelle vorhanden  -> null
```

Beispiel:

```txt
FMI Elfmeter: 75
SoFIFA Elfmeter: 72

combined_penalty = 74
```

---

## 13. Torwartwerte

Für Torhüter reichen 5 Torwartattribute:

```txt
1. Reflexe
2. Fangsicherheit
3. Eins-gegen-eins
4. Stellungsspiel
5. Passen
```

Interne Feldnamen:

```txt
gk_reflexes
gk_handling
gk_one_on_ones
gk_positioning
gk_passing
```

Torwartprofil:

```txt
gk_profile_100 =
    gk_reflexes     * 0.30
  + gk_handling     * 0.20
  + gk_one_on_ones  * 0.20
  + gk_positioning  * 0.20
  + gk_passing      * 0.10
```

Dann:

```txt
gk_profile_200 = gk_profile_100 * 2

pre_fit_strength_gk =
    match_base_strength * 0.80
  + gk_profile_200     * 0.20
```

Torwartattribute werden nicht für Feldspielerprofile verwendet.

---

## 14. Positionsprofile für Feldspieler

Die 13 Attribute werden positionsabhängig gewichtet. Das Positionsprofil bleibt zuerst auf 0–100 und wird danach auf 0–200 skaliert.

```txt
position_profile_100 = weighted_average(attributes_for_position)
position_profile_200 = position_profile_100 * 2
```

### Innenverteidiger

```txt
Zweikampf:          22 %
Defensivstellung:   22 %
Kopfball:           18 %
Kraft:              12 %
Teamwork:           10 %
Passspiel:           8 %
Tempo:               8 %
```

### Außenverteidiger

```txt
Tempo:              18 %
Ausdauer:           16 %
Zweikampf:          16 %
Defensivstellung:   14 %
Flanken:            14 %
Passspiel:          10 %
Technik:             8 %
Teamwork:            4 %
```

### Defensives Mittelfeld

```txt
Defensivstellung:   18 %
Zweikampf:          18 %
Passspiel:          16 %
Übersicht:          14 %
Ausdauer:           12 %
Teamwork:           10 %
Kraft:               6 %
Technik:             6 %
```

### Zentrales Mittelfeld

```txt
Passspiel:          20 %
Übersicht:          18 %
Technik:            14 %
Ausdauer:           12 %
Teamwork:           10 %
Defensivstellung:    8 %
Dribbling:           8 %
Zweikampf:           6 %
Tempo:               4 %
```

### Offensives Mittelfeld

```txt
Übersicht:          20 %
Technik:            18 %
Passspiel:          16 %
Dribbling:          14 %
Abschluss:          10 %
Teamwork:            8 %
Tempo:               8 %
Ausdauer:            6 %
```

### Flügelspieler

```txt
Tempo:              22 %
Dribbling:          20 %
Flanken:            16 %
Technik:            12 %
Abschluss:          10 %
Passspiel:           8 %
Ausdauer:            8 %
Übersicht:           4 %
```

### Stürmer

```txt
Abschluss:          24 %
Tempo:              14 %
Kopfball:           12 %
Technik:            12 %
Dribbling:          10 %
Teamwork:           10 %
Kraft:               8 %
Übersicht:           6 %
Ausdauer:            4 %
```

---

## 15. Mischung aus Tagesbasis und Positionsprofil

Die Tagesbasis aus Basis/Potential wird mit dem Positionsprofil gemischt.

```txt
pre_fit_strength =
    match_base_strength * 0.80
  + position_profile_200 * 0.20
```

Warum diese Mischung?

```txt
match_base_strength = allgemeines Leistungsniveau des Spielers an diesem Tag
position_profile = wie gut passt sein Attributprofil zur gespielten Rolle?
```

Wenn ein Spieler durch diese Mischung schwächer wird, ist das kein Fehler. Dann sagt das System:

```txt
Die sichtbare Headline-Stärke ist hoch, aber das Attributprofil passt für diese Position/Rolle nicht optimal.
```

---

## 16. Positions-Fit

Der Positions-Fit ist ein harter Multiplikator nach dem Positionsprofil.

| Fall | Faktor |
|---|---:|
| Hauptposition | 1.00 |
| Nebenposition | 0.90 |
| andere Feldposition | 0.70 |
| Feldspieler im Tor | 0.25 |
| Torwart im Feld | 0.30 |

Formel:

```txt
after_position_fit = pre_fit_strength * position_fit
```

---

## 17. Frische-Fit

Frische wird auf 0–100 gespeichert. Sie beeinflusst die Spielstärke als Multiplikator.

| Frische | Faktor |
|---:|---:|
| 95–100 | 1.02 |
| 85–94 | 1.00 |
| 75–84 | 0.97 |
| 65–74 | 0.93 |
| 50–64 | 0.87 |
| < 50 | 0.78 |

Formel:

```txt
after_freshness = after_position_fit * freshness_fit
```

---

## 18. Frischeverlust

Ausdauer steuert, wie stark ein Spieler durch Einsatzminuten Frische verliert.

Formel:

```txt
base_loss = 6 * (minutes_played / 90)

stamina_factor = clamp(
    1 + ((65 - stamina) / 100),
    0.75,
    1.35
)

freshness_loss = round(base_loss * stamina_factor * intensity_factor)
```

Beispiele bei 90 Minuten und normaler Intensität:

| Ausdauer | Frischeverlust |
|---:|---:|
| 90 | ca. 4–5 |
| 70 | ca. 6 |
| 50 | ca. 7 |
| 35 | ca. 8 |

Nach dem Spiel:

```txt
new_freshness = clamp(old_freshness - freshness_loss, 0, 100)
```

Regeneration kann später über Training, spielfreie Tage, medizinische Abteilung und Belastungssteuerung ergänzt werden.

---

## 19. RL-Form

RL-Form ist die reale Leistungsform eines Spielers anhand der letzten 10 möglichen Pflichtspiele.

Projektentscheidung:

```txt
Datenquelle: API-Football/API-Sports
Keine zweite Datenquelle
Kein Fallback
```

Für den MVP:

```txt
nur Vereinsspiele
keine Nationalmannschaft
keine Freundschaftsspiele
letzte 10 mögliche Pflichtspiele
Rating/Note und Minuten verwenden
```

Berechnung:

```txt
avg_rating = sum(rating * minutes_played) / sum(minutes_played)
```

Wenn ein Spieler in den letzten 10 Spielen gar keine Minuten hatte:

```txt
rl_form = -2
```

Wenn ein Spieler insgesamt weniger als 90 Minuten gespielt hat:

```txt
rl_form darf maximal 0 sein
```

Dadurch bekommt ein Spieler durch einen sehr kurzen Einsatz keine übertriebene Topform.

---

## 20. RL-Form-Skala

| Durchschnittsnote | RL-Form |
|---:|---:|
| >= 8.0 | +5 |
| 7.7–7.99 | +4 |
| 7.4–7.69 | +3 |
| 7.1–7.39 | +2 |
| 6.9–7.09 | +1 |
| 6.5–6.89 | 0 |
| 6.3–6.49 | -1 |
| 6.1–6.29 | -2 |
| 5.9–6.09 | -3 |
| 5.6–5.89 | -4 |
| < 5.6 | -5 |

---

## 21. RL-Form-Faktor

| RL-Form | Faktor |
|---:|---:|
| -5 | 0.94 |
| -4 | 0.95 |
| -3 | 0.96 |
| -2 | 0.98 |
| -1 | 0.99 |
| 0 | 1.00 |
| +1 | 1.01 |
| +2 | 1.02 |
| +3 | 1.04 |
| +4 | 1.05 |
| +5 | 1.06 |

Formel:

```txt
final_match_strength = after_freshness * rl_form_fit
```

---

## 22. Verletzungsstatus

Verletzungen verändern nicht die Stärke. Sie verändern nur die Verfügbarkeit.

Status:

```txt
fit
verletzt
gesperrt
```

Regeln:

```txt
fit       -> aufstellbar
verletzt  -> nicht aufstellbar
gesperrt  -> nicht aufstellbar
```

Kein System mit:

```txt
angeschlagen, aber 80 % Stärke
```

Das bleibt bewusst draußen, damit das System einfach und nicht frustrierend wird.

---

## 23. Dynamisches Verletzungsrisiko

Das Verletzungsrisiko steigt dynamisch mit niedriger Frische. Es gibt keinen harten Cut bei 70.

Formel:

```txt
base_risk_per_90 = 0.006

freshness_factor = 1 + ((100 - freshness) / 40)²

stamina_factor = clamp(
    1 + ((70 - stamina) / 200),
    0.85,
    1.25
)

injury_risk_per_90 =
    base_risk_per_90
  * freshness_factor
  * stamina_factor
  * intensity_factor
```

Für Einsatzminuten:

```txt
injury_risk = 1 - (1 - injury_risk_per_90) ^ (minutes_played / 90)
```

Beispiele bei 90 Minuten, Ausdauer 70 und normaler Intensität:

| Frische | Risiko pro 90 Minuten |
|---:|---:|
| 100 | 0,60 % |
| 90 | 0,64 % |
| 80 | 0,75 % |
| 70 | 0,94 % |
| 55 | 1,36 % |
| 40 | 1,95 % |
| 25 | 2,71 % |
| 10 | 3,64 % |

Das Risiko ist spürbar, aber nicht übertrieben.

---

## 24. Verletzungsdauer in Tagen

Verletzungsdauer wird in Tagen gespeichert, nicht in Spielen.

Ziel: Verletzungen sollen relevant sein, aber kein Frustfaktor werden.

Maximale Verletzungsdauer:

```txt
60 Tage
```

Gewichtung:

| Kategorie | Dauer | Wahrscheinlichkeit |
|---|---:|---:|
| leicht | 1–5 Tage | 75 % |
| mittel | 6–14 Tage | 18 % |
| schwer | 15–35 Tage | 6 % |
| sehr schwer | 36–60 Tage | 1 % |

Umsetzung:

```txt
injury_days = weighted_random_duration()
injured_until = current_date + injury_days
```

Wenn:

```txt
injured_until >= current_date
```

ist der Spieler verletzt und nicht aufstellbar.

Wenn:

```txt
injured_until < current_date
```

ist der Spieler wieder fit.

---

## 25. Pseudocode

### Kombinieren von Quellwerten

```python
def combine_source_values(*values):
    valid_values = [value for value in values if value is not None]

    if not valid_values:
        return None

    return round(sum(valid_values) / len(valid_values))
```

### Basis und Potential

```python
def calculate_base_strength(fmi_rating, sofifa_rating):
    return int(fmi_rating) + int(sofifa_rating)


def calculate_potential(base_strength, fmi_potential, sofifa_potential):
    potential = int(fmi_potential) + int(sofifa_potential)
    return max(base_strength, potential)
```

### Match-Basis

```python
import random


def draw_match_base_strength(base_strength, potential):
    potential = max(base_strength, potential)
    return random.randint(base_strength, potential)
```

### Positionsprofil

```python
def weighted_average(attributes, weights):
    total_weight = 0
    total_value = 0

    for attr_name, weight in weights.items():
        value = attributes.get(attr_name)
        if value is None:
            continue

        total_value += value * weight
        total_weight += weight

    if total_weight == 0:
        return None

    return total_value / total_weight
```

### Positions-Fit

```python
def get_position_fit(player, played_position):
    if player.primary_position == "GK" and played_position != "GK":
        return 0.30

    if player.primary_position != "GK" and played_position == "GK":
        return 0.25

    if played_position == player.primary_position:
        return 1.00

    if played_position in player.secondary_positions:
        return 0.90

    return 0.70
```

### Frische-Fit

```python
def get_freshness_fit(freshness):
    if freshness >= 95:
        return 1.02
    if freshness >= 85:
        return 1.00
    if freshness >= 75:
        return 0.97
    if freshness >= 65:
        return 0.93
    if freshness >= 50:
        return 0.87
    return 0.78
```

### RL-Form-Fit

```python
def get_rl_form_fit(rl_form):
    mapping = {
        -5: 0.94,
        -4: 0.95,
        -3: 0.96,
        -2: 0.98,
        -1: 0.99,
         0: 1.00,
         1: 1.01,
         2: 1.02,
         3: 1.04,
         4: 1.05,
         5: 1.06,
    }
    return mapping.get(rl_form, 1.00)
```

### Finale Spielstärke

```python
def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def calculate_final_match_strength(
    match_base_strength,
    position_profile_100,
    position_fit,
    freshness_fit,
    rl_form_fit,
):
    position_profile_200 = position_profile_100 * 2

    pre_fit_strength = (
        match_base_strength * 0.80
        + position_profile_200 * 0.20
    )

    final_strength = (
        pre_fit_strength
        * position_fit
        * freshness_fit
        * rl_form_fit
    )

    return clamp(round(final_strength), 1, 200)
```

### Verletzungsrisiko

```python
def injury_risk_for_minutes(
    freshness,
    stamina,
    minutes_played,
    intensity_factor=1.0,
):
    freshness = clamp(freshness, 1, 100)
    stamina = clamp(stamina, 1, 100)
    minutes_played = clamp(minutes_played, 0, 120)

    base_risk_per_90 = 0.006

    freshness_factor = 1 + ((100 - freshness) / 40) ** 2
    stamina_factor = clamp(1 + ((70 - stamina) / 200), 0.85, 1.25)

    injury_risk_per_90 = (
        base_risk_per_90
        * freshness_factor
        * stamina_factor
        * intensity_factor
    )

    return 1 - ((1 - injury_risk_per_90) ** (minutes_played / 90))
```

### Verletzungsdauer

```python
def draw_injury_duration_days(rng=random):
    roll = rng.random()

    if roll < 0.75:
        return rng.randint(1, 5)

    if roll < 0.93:
        return rng.randint(6, 14)

    if roll < 0.99:
        return rng.randint(15, 35)

    return rng.randint(36, 60)
```

---

## 26. Empfohlene Datenbankfelder

### Source-Felder

```txt
fmi_url
sofifa_url
transfermarkt_url

fmi_rating
sofifa_rating
fmi_potential
sofifa_potential

fmi_tempo
sofifa_tempo
fmi_ausdauer
sofifa_ausdauer
fmi_kraft
sofifa_kraft
fmi_technik
sofifa_technik
fmi_dribbling
sofifa_dribbling
fmi_passspiel
sofifa_passspiel
fmi_flanken
sofifa_flanken
fmi_abschluss
sofifa_abschluss
fmi_kopfball
sofifa_kopfball
fmi_zweikampf
sofifa_zweikampf
fmi_defensivstellung
sofifa_defensivstellung
fmi_uebersicht
sofifa_uebersicht
fmi_teamwork
sofifa_teamwork

fmi_ecken
sofifa_ecken
fmi_freistoss
sofifa_freistoss
fmi_elfmeter
sofifa_elfmeter

fmi_gk_reflexes
sofifa_gk_reflexes
fmi_gk_handling
sofifa_gk_handling
fmi_gk_one_on_ones
sofifa_gk_one_on_ones
fmi_gk_positioning
sofifa_gk_positioning
fmi_gk_passing
sofifa_gk_passing
```

### Berechnete Spielerfelder

```txt
base_strength_200
potential_200
potential_gap

attr_tempo
attr_ausdauer
attr_kraft
attr_technik
attr_dribbling
attr_passspiel
attr_flanken
attr_abschluss
attr_kopfball
attr_zweikampf
attr_defensivstellung
attr_uebersicht
attr_teamwork

set_piece_corners
set_piece_free_kick
set_piece_penalty

gk_reflexes
gk_handling
gk_one_on_ones
gk_positioning
gk_passing

freshness
rl_form
injured_until
suspension_until
```

### Match-bezogene Felder

```txt
match_id
player_id
played_position
base_strength_200
potential_200
match_base_strength
position_profile_100
position_profile_200
position_fit
freshness_fit
rl_form_fit
pre_fit_strength
final_match_strength
minutes_played
freshness_loss
injury_risk
injury_happened
injury_days
```

---

## 27. Akzeptanzkriterien für Replit

Die Implementierung gilt als korrekt, wenn folgende Punkte erfüllt sind:

```txt
[ ] FMI- und SoFIFA-Rohwerte werden getrennt gespeichert.
[ ] Leere Quellenwerte werden als null gespeichert, nicht als 0.
[ ] Kombinierte Attribute ignorieren null-Werte korrekt.
[ ] Basisstärke wird als FMI Rating + SoFIFA Rating berechnet.
[ ] Potential wird als FMI Potential + SoFIFA Potential berechnet.
[ ] Potential ist niemals kleiner als Basisstärke.
[ ] Pro Match wird pro Spieler genau eine Tagesbasis zwischen Basis und Potential gezogen.
[ ] Tagesbasis wird gespeichert und bei Reloads nicht neu gewürfelt.
[ ] Positionsprofil wird aus den 13 Attributen positionsabhängig berechnet.
[ ] Feldspieler und Torhüter nutzen unterschiedliche Profilberechnungen.
[ ] Positions-Fit wirkt nach dem Positionsprofil.
[ ] Frische-Fit wirkt nach dem Positions-Fit.
[ ] RL-Form-Fit wirkt nach dem Frische-Fit.
[ ] Finale Spielstärke ist immer zwischen 1 und 200.
[ ] Frischeverlust hängt von Minuten, Ausdauer und Intensität ab.
[ ] Verletzungsrisiko steigt dynamisch mit sinkender Frische.
[ ] Verletzungen dauern 1 bis maximal 60 Tage.
[ ] Verletzungen verändern nicht die Stärke, sondern nur die Aufstellbarkeit.
[ ] Sperren verändern nicht die Stärke, sondern nur die Aufstellbarkeit.
[ ] Source-Abweichungen über 30 Punkten werden als Mapping-Warnung markiert.
```

---

## 28. Kurzfassung

```txt
Basisstärke = FMI Rating + SoFIFA Rating
Potential = FMI Potential + SoFIFA Potential
Tagesbasis = zufälliger Wert zwischen Basis und Potential
Attribute = Durchschnitt aus FMI und SoFIFA, null-sicher
Positionsprofil = gewichteter Attributschnitt je Position
Vor-Fit-Stärke = 80 % Tagesbasis + 20 % Positionsprofil_200
Finale Stärke = Vor-Fit-Stärke × Positions-Fit × Frische-Fit × RL-Form-Fit
Verletzungsrisiko = dynamisch nach Frische, Ausdauer, Minuten
Verletzungsdauer = 1–60 Tage, meistens 1–5 Tage
```
