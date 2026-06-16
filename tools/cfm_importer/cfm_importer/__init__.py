"""CFM-Importer — lokales Windows-Tool für den Vereins-/Spielerimport.

Läuft ausschließlich lokal auf einem Windows-PC, öffnet einen sichtbaren
Microsoft Edge (Playwright, persistentes Profil), liest Transfermarkt,
FMInside und SoFIFA aus und überträgt die Rohdaten über die geschützte
Token-API an den Creator-Mode des Websoccer-Servers.

Das Tool berechnet KEINE finalen Attribute und importiert KEINE Bilder — die
serverseitige Engine ist dafür maßgeblich. Lokale State-Dateien dienen nur der
Wiederaufnahme nach Abbruch.
"""

__version__ = '1.0.0'
