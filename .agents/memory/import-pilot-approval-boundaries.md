---
name: Import-Pilot Freigabegrenzen
description: Verbindliche Anker-/Feldlistenregeln aus Nachtrag 5 sowie fortgeltende Schutz-, Konten- und Isolationsentscheidungen.
---

Nachtrag 8 hat bei Widersprüchen Vorrang vor Teil A, B, C und Nachträgen 1–7. Club, Player und Stadium bleiben die Spielanker; keine neuen Modelle daneben mit späterem Umhängen der Module. Bestehende Tabellen erweitern/reparieren, neue nur bei echter Lücke. Jedes Feld einer Schicht und einem kontrollierten Schreibrecht zuordnen; Spiegel einzeln begründen. Nach Ligastart gilt die bestätigte konkrete Positivliste, nicht pauschal „Echtweltdaten überschreiben“.

**Why:** Der Nutzer lehnt die Zwischenstufe ab, in der nach dem Reset die echten Spielanker leer und die Module noch nicht umgehängt wären.

**How to apply:** T2 ist abgenommen. Nachtrag 8 autorisiert T3 und T4 in einem Zug mit anschließendem Halt; T5/Reset, Dortmund-Szenensicherung und Stärkeformeländerungen bleiben gesperrt. Ein ausdrücklich auf Paket-Nachpflege begrenzter Auftrag startet diese App-Arbeiten nicht. Der Pilot lädt die vollständige game-App und dieselben echten Migrationen wie später live. Kein Hetznerzugriff und keine Deploy-Sperre: Mark übernimmt manuell per GitHub-Push, Server-Pull und Deploy. Redundante Spalten später modulweise abbauen.

Nur importierte Vereine stehen in Club. Fremde Historien-/Rekord-/Leihvereine bleiben TM-ID plus Originalname; spätere FK-Verknüpfung ist auch nach Ligastart erlaubt. Der operative Leihstand gehört nach Initialisierung ausschließlich dem Spiel; der Erhebungsstand gehört ins Paketarchiv. Haupt-/Nebenpositionen einschließlich ihrer Spiegel bleiben bei Vereinspaket-Reupload nach Ligastart ebenso gesperrt wie Ratings.

**Why:** Der Nutzer hat Verweis-Club-Zeilen und doppelte Real-Leihstände ausdrücklich verworfen; Positionsänderungen sind für den späteren spielerbezogenen Aktualisierungsweg vorgesehen.

**How to apply:** Keine NULL-/Platzhalterliga, keine historischen Mini-Clubs, kein zweiter Stammverein aus real_life_club. Fehlende Vereins-FKs sind kein Anlass für Namensmatching oder erfundene IDs. Paketmaske nach Ligastart nicht eigenmächtig erweitern.

Fortgeltende Isolation: eigene Pilot-Rolle, effektiver Schreibschutz nach public, keine Rechteänderung an der Bestandsrolle. Ausnahme aus Nachtrag 7: additive gemeinsame Migrationen laufen jetzt auch auf public; neue Spalten und zwei leere Tabellen sind erlaubt, bestehende Daten bleiben erhalten.

**Why:** Der Nutzer hat diese Richtung ausdrücklich gewählt und gegenseitige harte Rollenabschirmung verworfen.

**How to apply:** Der Nutzer hat am 2026-10-05 den tatsächlichen Isolationsnachweis und die korrigierte Kontenliste bestätigt. Diese Isolation nicht durch Eingriffe in die Bestandsrolle ersetzen. Der Weg „Replit-Datenbank sichern und direkt leeren“ wurde verworfen.

Die bestätigte Schutzliste umfasst elf Regeln-/Parametertabellen: zusätzlich zu den neun der Vorprüfung NeutralVenue vollständig und LandKoeffizient ausschließlich Saison 0. Nachtrag 4 autorisiert ihre Kopie sowie Schiedsrichter-/Sponsorenkatalog und bestätigte Konten/Profile; keine alten Spiele, Sim-Zähler, Sponsorenverträge, Angebote oder Erträge.

**Why:** Explizite Erweiterung in N16 und Kopierfreigabe in N18–N22.

**How to apply:** Aktuellen konsistenten Quellstand prüfen. Manager-Startwerte ausdrücklich level=1, xp=0, xp_max=800, nicht den früheren Vorschlag Level 0/alte Schwelle verwenden. Übrige N17-Feldentscheidungen sind bestätigt; Notizen und Support-Tickets weder im Pilot noch beim Live-Reset übernehmen. Vor Kontokopie fehlende Rechte-Zielmodelle und Profile ohne Login melden und nicht selbst entscheiden.

Der Modellplan muss die Wiederverwendung von strength_service/strength_engine ohne Formelkopie oder Formeländerung beibehalten. N27 ersetzt den früheren Einseitenplan durch eine Feldliste mit Tabelle/Spalte, Zustand, Schicht/Schreiber, Spiegel/Quelle/Funktion und erneutem Upload nach Ligastart.

**Why:** Der Nutzer verlangt in N22 ausdrücklich, dass aus dem isolierten Pilot kein zweites Spiel neben dem Spiel entsteht.

**How to apply:** Einen gemeinsamen Spiel-/Berechnungscode vorsehen, keine Pilot-Kopie der Stärkeformeln oder komplette zweite Spiel-App bauen. Der Modellplan ist ein Freigabegegenstand, kein Auftrag zur vorgezogenen Modellimplementierung.

Rechte für im Pilot noch nicht geladene Zielmodelle als Metadaten erhalten, ohne diese Modelle dafür zu aktivieren.

**Why:** Der Nutzer hat nach der vorgeschriebenen Meldung der fehlenden Rechte-Zielmodelle ausdrücklich „Als Metadaten erhalten (empfohlen)“ gewählt.

**How to apply:** Natürliche Schlüssel erhalten und technische IDs zuordnen; keine Rechte verwerfen und keine Spielmodelle oder Rechteauswertung allein zur Katalogübernahme einschalten. Die Entscheidung hebt den Halt vor der Modellplan-Freigabe nicht auf.

Die vorhandenen Pilot-Secrets verwenden; ihre Übernahme nicht an einer starren 32-Zeichen-Grenze blockieren.

**Why:** Der Nutzer hat ausdrücklich angeordnet, die Werte auch mit 28, 30 oder 31 Zeichen zu übernehmen.

**How to apply:** Nicht leere, vom Bestand getrennte Pilot-Zugangsdaten und Rollenbeschränkungen beibehalten, aber nicht erneut wegen dieser Mindestlänge Ersatzwerte verlangen. Identische Eingaben innerhalb des Piloten erfordern keine weitere Eingaberunde; die Sitzungs-Signierung zweckgebunden ableiten.

real_life_club wird im neuen Modus sofort stillgelegt, nicht zum Stammvereins-Spiegel. Vier Lesergruppen und die Altschreiber auf owner_club beziehungsweise externe TM-ID/Originalname umstellen; nur Altmodus erhält bisheriges Verhalten.

**Why:** Der Nutzer hat den vorgeschlagenen vorläufigen Spiegel ausdrücklich nicht gewählt.

**How to apply:** Teil von T2, nicht auf die Anzeigephase verschieben. Die physische Spalte bleibt bis späterem Aufräumen.

Fehlende Spieler bei erneutem Paketupload vor Ligastart bleiben mit Identität, IDs, Quellwerten und Historie erhalten, verlassen den Spielverein und kommen in einen eigenen nicht scoutbaren Prüfpool mit Info-Arbeitslisteneintrag.

**Why:** Der Nutzer hat den Prüfpool gewählt, nicht Löschen oder freie Scouting-Freigabe.

**How to apply:** Nach Ligastart keinen Kaderabgleich. Vorstart-Wiederzuordnung per TM-ID in einem anderen Vereinspaket oder kontrolliert über die Arbeitsliste; danach normale Poolregeln.
