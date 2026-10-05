# Import-Neuaufbau: Nachtrag 4 zur Übergabe

Stand: 05.10.2026 · gehört zu `Import_Neuaufbau_Uebergabe_Replit.md`, den Nachträgen 1 bis 3 und zu Replits „T1: Tatsächlicher Isolationsnachweis" samt „N17: Konten-Feldliste zur Bestätigung"

Dieser Nachtrag bestätigt den Isolationsnachweis und die Konten-Feldliste mit einer Änderung. Er hat bei Widersprüchen Vorrang vor Teil A, Teil C und den Nachträgen 1 bis 3. Am BVB-Referenzpaket ändert er nichts.

Alle Entscheidungen hat Mark am 05.10.2026 einzeln getroffen.

## Entscheidungen

| # | Entscheidung |
|---|---|
| N18 | **Der Isolationsnachweis vom 05.10.2026, 22:04 Uhr, ist bestätigt.** Der Pilot läuft im Schema `import_pilot` mit der Rolle `import_pilot_role`. N5, N14 und N15 bleiben. Der Weg „Replit-Datenbank sichern und direkt leeren" wurde erwogen und verworfen, nachdem das Schema fertig eingerichtet war |
| N19 | **Konten-Feldliste, Level:** Statt Replits Vorschlag (Level 0, alte Schwelle) gelten die Startwerte aus dem XP-Konzept: `level` = 1, `xp` = 0, `xp_max` = 800. Das ist der Zustand eines frisch angelegten Managers |
| N20 | **Notizen und Support-Tickets werden nicht übernommen** (`game_managernotes`, `game_supportticket`). Gilt für den Pilot und den Live-Reset |
| N21 | **Der Rest der Konten-Feldliste ist wie von Replit vorgelegt bestätigt.** Übersicht unten |
| N22 | **Ablauf in T1:** Replit kopiert jetzt die Schutzbereiche und legt zusammen mit dem Kopierbericht einen Modellplan vor. Danach ein Halt. Das fachliche Datenmodell beginnt erst nach Marks Freigabe des Modellplans |

## Zu N19 und N21: Bestätigte Feldliste Managerprofil

**Bleibt:** `id`, `user_id`, `name`, `trainer_type`, `nationality_flag`, `nationality_name`, `member_since`, `birth_date`, `profile_image`, `name_confirmed`, `residence`, `visibility_settings`

**Startwerte:**

| Feld | Wert |
|---|---|
| `level` | 1 |
| `xp` | 0 |
| `xp_max` | 800 |
| `highscore` | leerer Anzeigewert „–" |
| `active_title` | NULL |
| `title_progress` | `{}` |
| `season_score`, `previous_season_score` | 0 |
| `inactivity_season_count`, `inactivity_streak` | 0 |
| `transfer_ban_until` | NULL |
| `login_streak`, `login_points_today` | 0 |
| `login_last_date` | NULL |
| `login_day14_awarded`, `login_day30_awarded`, `login_day30_money_paid` | false |
| `last_seen` | NULL |
| `favourite_club_id` | NULL |

**Nicht kopiert:** `updated_at` (wird neu erzeugt)

Folgen, von Mark so bestätigt: Sanktionszähler und Transfersperren verfallen mit dem Neustart. Coin-Guthaben beginnt bei 0. Der Lieblingsverein wird neu gewählt.

**Konto und Rechte:** `auth_user`, `auth_group`, Gruppenzuordnungen und Einzelrechte bleiben. Rechte und ContentTypes werden nach natürlichem Schlüssel (`app_label`, `model`, `codename`) zugeordnet, nicht nach ID. Sitzungen und Migrationsstand des Bestands werden nicht kopiert.

**Nicht kopiert:** alle 35 von Replit aufgeführten Tabellen mit direktem Bezug auf Konto oder Managerprofil sowie die aufgeführten indirekten Historientabellen (Spielereignisse, Geschichten, Freundschaftsspiele, Community-Turniere, Rekordbrüche, Auktions-Beobachtungen).

Vor der Kontokopie zu melden, nicht selbst zu entscheiden:

- Rechte, die auf ein Modell zeigen, das es im Ziel nicht gibt
- Managerprofile ohne verknüpftes Login-Konto

## Zu N22: Was der Modellplan beantwortet

Der Pilot lädt derzeit nur `import_pilot` und die Sitzungen, die Spiel-App `game` nicht. Für die Trennung ist das richtig. Für das Datenmodell darf daraus kein zweites Spiel neben dem Spiel werden. Der Modellplan ist höchstens eine Seite und beantwortet:

1. In welcher App und in welchen Dateien liegen die neuen Modelle nach B6?
2. Wie benutzt die bestehende Stärkeberechnung (`strength_service`, `strength_engine`) die neuen Quellwerte, ohne dass eine Formel geändert oder kopiert wird?
3. Wie kommen die Pilot-Seiten aus T4 (Verein, Stadion, Kader, Spielerprofil, Ruhmeshalle) an die neuen Daten?
4. Wie kommen die neuen Modelle später in die laufende Anwendung: ein Code, zwei Schemata, oder ein Umzug?
5. Welche alten Modelle bleiben vorerst im Code stehen, und was passiert mit ihren Tabellen im Pilot-Schema?

## Freigabe

Freigegeben ist die Kopie der Schutzbereiche in das Pilot-Schema, aus einem neuen, konsistenten Quellstand:

- Schiedsrichter-Katalog, ohne alte Spiele und Sim-Zähler
- Sponsoren-Katalog, ohne alte Verträge, Angebote und Erträge
- Konten und Profil nach N6, N19, N20, N21
- die elf Tabellen „Regeln und Parameter" nach N16 (am 05.10.2026 zusammen 137 Zeilen; `game_neutralvenue` ist in Replit leer, `game_landkoeffizient` hat 9 Zeilen für Saison 0)

Nicht freigegeben bis zur Freigabe des Modellplans: fachliches Datenmodell, Paketimport, Sicherung der Dortmund-Szene. T2–T5 bleiben gesperrt. Hetzner bleibt unberührt.
