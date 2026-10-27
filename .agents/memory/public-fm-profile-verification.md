---
name: Öffentliche FM-Profilprüfung
description: Grenzen extrahierter FMInside-Seiten und UID-basierter Geburtstagsgegenprüfung.
---

Bei einer manuellen FMInside-Identitätsprüfung fehlende Angaben im
extrahierten Haupttext nicht als fehlende Angaben auf der Originalseite
interpretieren. Die Extraktion kann die gesamte Profil-Seitenleiste auslassen.
Kaderlisten einschließlich Nachwuchs können ein passendes Profil unter einem
Kurznamen auffindbar machen, das eine Vollnamenssuche übersieht.

**Why:** Bei der spanischen Quellenprüfung lieferte der Haupttext Attribute und
FAQ, aber nicht die Profil-Seitenleiste. Eine direkte Kaderprüfung fand ein
separates Jugendprofil, während die Namenssuche keine belastbare ID lieferte.

**How to apply:** Kandidaten aus tatsächlich gelesenen Kaderlinks übernehmen,
dann die genaue UID und das Geburtsdatum in einer weiteren öffentlichen
FM-Datenbankdarstellung gegenprüfen. Diese zweite Darstellung belegt den
FM-Datenstand, nicht den tatsächlichen Geburtstag. Geburtstagsabweichungen
gegen reale Identitätsquellen ausdrücklich als Konflikt behandeln, nicht
durch Name, Alter oder Vereinsnähe stillschweigend übergehen.

Eine bloße Anzeige „dynamisches Potenzial“ belegt keine numerische Obergrenze.
Diese nicht aus Sternebewertungen, verbleibender Entwicklung oder dem
Potenzial eines ähnlich benannten Spielers ableiten.

Öffentliche ID-Suchindizes können versionsübergreifend sein und Treffer mit
leerer FM-UID enthalten. Ein internes Indexfeld `id` ist dann kein Ersatz
für `fm_id`; ein Name-/Vereinstreffer ohne UID und Geburtstag bleibt nur ein Hinweis.

**Why:** Die öffentliche FMRef-Suche enthielt einen passenden Kurznamen mit
leerem UID-Feld sowie einen Namensvetter, der nur in einem älteren
Community-Update statt im gesuchten FM26-Profildatenstand belegt war.

**How to apply:** Kurznamensvarianten auch vereinsübergreifend prüfen,
vollständig paginieren und Suchtreffer anschließend am versionsbezogenen
Profil mit UID und exaktem Geburtstag bestätigen. Versionsübergreifende
Suchtreffer und interne Indexnummern niemals als FM26-Identitätsnachweis übernehmen.

**Why:** Bei der Quellenprüfung war eine Identität mit exaktem Geburtstag
belegt, während die gelesenen öffentlichen Quellen die numerische
Potenzialgrenze nicht belegten. Identitätsfreigabe und vollständige
spielbare Stärkedaten sind unterschiedliche Nachweise.

**How to apply:** Die richtige ID und belegte Werte dürfen getrennt von einer
weiterhin nötigen Datensperre nachgepflegt werden. Unbelegte Werte bleiben
NULL; eine fehlende Berechenbarkeit ausdrücklich als offenen Grund ausweisen.
