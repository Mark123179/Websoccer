---
name: Import-Pilot Freigabegrenzen
description: Verbindliche Trennungsrichtung und Freigabehalte aus Nachtrag 3.
---

Nachtrag 3 hat bei Widersprüchen Vorrang vor Teil A/C und Nachträgen 1/2. Die Trennung erfolgt über eine neue Pilot-Rolle; bestehende Rollen, Verbindungen, Einstellungen und Prozesse bleiben unangetastet. Pilot → public braucht effektiven Schreibschutz; Bestand → Pilot wird über Suchpfad, Code, Befehle und laufende Prozesse belegt, nicht durch Rechteentzug im Bestand.

**Why:** Der Nutzer hat diese Richtung ausdrücklich gewählt und gegenseitige harte Rollenabschirmung verworfen.

**How to apply:** Zuerst ausschließlich technische Isolation einrichten. Tatsächlichen Nachweis und die vollständige Konten-Feldklassifikation gemeinsam vorlegen, danach Halt. Schutzbereich-/Kontokopie und fachliches Datenmodell benötigen separate Bestätigung. Paketimport, Szenensicherung, spätere Phasen und Hetzner sind nicht durch die Isolationsfreigabe erlaubt.

Die bestätigte Schutzliste umfasst elf Tabellen: zusätzlich zu den neun der Vorprüfung NeutralVenue vollständig und LandKoeffizient ausschließlich Saison 0. Diese Bestätigung autorisiert noch keine Kopie.

**Why:** Explizite Erweiterung durch den Nutzer in N16.

**How to apply:** Vor späterer Kopie aktuelle Quellstände prüfen. N17 klassifiziert jedes Profilfeld und jede managerbezogene Tabelle zur Bestätigung; nicht-nullbare Resetwerte ausdrücklich nennen. Level soll nach N6 bei 0 beginnen; den Bestandsdefault 1 nicht still übernehmen.

Die vorhandenen Pilot-Secrets verwenden; ihre Übernahme nicht an einer starren 32-Zeichen-Grenze blockieren.

**Why:** Der Nutzer hat ausdrücklich angeordnet, die Werte auch mit 28, 30 oder 31 Zeichen zu übernehmen.

**How to apply:** Nicht leere, vom Bestand getrennte Pilot-Zugangsdaten und Rollenbeschränkungen beibehalten, aber nicht erneut wegen dieser Mindestlänge Ersatzwerte verlangen. Identische Eingaben innerhalb des Piloten erfordern keine weitere Eingaberunde; die Sitzungs-Signierung zweckgebunden ableiten.
