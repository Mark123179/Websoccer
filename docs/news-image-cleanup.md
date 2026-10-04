# Verwaiste News-Bilder sicher bereinigen

Uploads werden vor dem News-Datensatz gespeichert. Ein späterer Upload-, Sicherungs-
oder Datenbankfehler kann deshalb unreferenzierte Bilder hinterlassen.
Die Bereinigung erfolgt **nur explizit**, niemals beim Lesen oder Veröffentlichen.
Profilbilder und andere Upload-Verzeichnisse werden nicht verändert.

## Vorschau

```sh
python manage.py cleanup_news_images
python manage.py cleanup_news_images --min-age-days 30
```

Der Standard ist sieben Tage; kürzere Fristen werden abgelehnt. Zeitbasis ist der
letzte Änderungs-/Erstellungszeitpunkt des Objekts (lokal einschließlich ctime).
Fehlende oder unlesbare Metadaten bedeuten Abbruch, nicht „alt genug“.
Die Ausgabe nennt Kandidaten mit Speicherort und Alter sowie geschützte Dateien.
Es werden keine Dateien oder Datenbankzeilen geschrieben.

## Löschlauf

1. Vorschau prüfen. Vor einer echten Bereinigung ein reguläres Speicherbackup anlegen.
2. News-Veröffentlichungen, Bearbeitungen, Bildmigrationen **und Wiederherstellungen**
   pausieren, laufende Vorgänge vollständig beenden. Alle Web-/Worker-Prozesse, die
   News schreiben können, müssen pausiert bleiben. Den Befehl in einem separaten
   Prozess mit denselben Datenbank- und Speichereinstellungen ausführen.
3. Erst dann ausdrücklich bestätigen:

   ```sh
   python manage.py cleanup_news_images --apply --confirm-writers-stopped
   ```

4. Ergebnis prüfen und Schreibprozesse wieder freigeben.

Die Bestätigung ist eine Bedienerbestätigung, kein technischer Wartungsmodus.
Datenbank und Dateispeicher haben keine gemeinsame Transaktion. Die Wartefrist
allein schützt nicht vor einer gleichzeitigen Veröffentlichung, die eine alte
Bild-URL wiederverwendet. Daher ist ein Löschlauf bei aktiven Schreibern unzulässig.
Eine Löschung ist endgültig; bei einem späteren Fehler bleiben bereits gemeldete
Löschungen bestehen.

## Schutzregeln

- Nur Dateien unter `news-images/` werden berücksichtigt.
- Sämtliche JSON-Zeichenketten in `ClubNewsItem.card_data` und `blocks` sowie
  historische `img_path`- und `thumbnail_static_path`-Referenzen werden konservativ geprüft. Relative,
  absolute und URL-kodierte Media-URLs mit Query/Fragment werden berücksichtigt.
- Jede private Datei unter `news-image-backups/` muss als vollständige Sicherung
  lesbar sein. Bildreferenzen aus **before und after** bleiben geschützt, auch
  nach Wiederherstellung oder Löschung des Beitrags. Sicherungen werden niemals
  gelöscht, öffentlich ausgegeben oder verändert.
- Unlesbare/unbekannte Sicherungen, Inventarfehler, Datenbankfehler oder unsichere
  Pfade verhindern den Start der Löschung. Symlinks werden nicht verfolgt.
- Vor jeder Löschung werden alle Referenzen und Sicherungen erneut gelesen.
  Veränderte Dateien werden übersprungen. Bucket-Löschungen verwenden zusätzlich
  eine serverseitige Objektversionsbedingung; Löschfehler werden nicht verschluckt.
- Bei Replit-Speicher werden auch lokale historische News-Bilder und Sicherungen
  unter `MEDIA_ROOT` berücksichtigt, da das Media-Serving beide Speicher liest.
  Gleichnamige Referenzen schützen beide Kopien. Kein stiller Speicher-Fallback.

Beschädigte Sicherungen müssen vor einem neuen Versuch geprüft/repariert werden;
sie einfach zu entfernen kann den Wiederherstellungsschutz verlieren.
Nicht unterstützte Speicheranbieter werden abgelehnt.