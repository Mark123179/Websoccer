# Schiedsrichterstatistik in der Spielvorschau

Die drei bestehenden Kacheln werden gemeinsam um 88 Artboard-Pixel angehoben,
bis auf einen kleinen Abstand zum Kalender.
Bei umgebrochenem Kalender wird der gemeinsame Kachelbeginn an dessen tatsächliche
Höhe angepasst; die Kacheln dürfen den Kalender nicht verdecken.
Die Breiten, Kalenderposition, Kabine und historischen Schiedsrichterprofile bleiben erhalten.

Unter dem angesetzten Schiedsrichter erscheint die Statistik der aktuellen
numerischen Sim-Saison. Grundlage sind ausschließlich gespeicherte Spielberichte.
Keine Simulation, historische Ersatzwerte oder Schreibvorgänge beim Seitenaufruf.

Der Nutzer hat den Vergleich ausdrücklich auf alle Schiedsrichter der gesamten
Simulation erweitert: alle Wettbewerbe, nicht nur die Liga des angezeigten Spiels.
Verglichen werden Häufigkeiten pro Spiel, nicht absolute Saisonmengen.
Der gemeinsame Durchschnitt ist einsatzgewichtet. Mindestens fünf auswertbare
Einsätze und zwei Schiedsrichter sind für eine farbliche Bewertung erforderlich.
Abweichungen: mindestens 25 % niedriger = Grün, 25 % höher = Gelb,
50 % höher = Rot. Bei Durchschnitt null bleibt der Wert neutral.
Die Schwellen verändern ausschließlich die Anzeige, nicht die Match-Engine.

Anzeigen: Spiele, Ø Gelb, Rot, Elfmeter-Tore und Umstritten.
Elfmeter-Tore umfassen reguläre Spielzeit und Verlängerung, nicht Elfmeterschießen.
Verhängte Elfmeter insgesamt und umstrittene Entscheidungen sind nicht vollständig
gespeichert. Daher genaue Benennung bzw. „—“ statt erfundener Nullwerte.
Unvollständige historische Berichte bleiben ebenfalls explizit nicht erfasst.
Keine Einsätze und fehlender Saisonstatus erhalten klare Hinweistexte.

Browserlokale Layouts bleiben erhalten und werden gezielt um den Statistikblock
ergänzt. Backendtests prüfen Saisonfilter, globale Vergleichsbasis, Einsatzmengen,
Farbgrenzen, Datenlücken, Elfmeterschießen und tatsächliche Template-Ausgabe.
Layoutprüfung erfolgt mit gerendertem Django-HTML und den aktuellen App-Assets.
