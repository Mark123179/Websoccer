# Eigene News-Bilder

Neue Veröffentlichungen speichern validierte PNG-, JPEG-, GIF- und WebP-Dateien
im bestehenden Django-Medienbackend unter `news-images/`. Im News-JSON stehen
nur URLs. Kartenbild und Bildbausteine nutzen denselben Ablauf. Externe Bild-URLs
werden nicht heruntergeladen. Ein Speicherfehler verhindert die Veröffentlichung
und wird dem Nutzer angezeigt; es gibt keinen stillen Wechsel ins lokale Dateisystem.

## Speicherbetrieb

Grundlage: [App Storage Python SDK](https://docs.replit.com/features/sdks/object-storage-python-sdk)
und [App Storage](https://docs.replit.com/features/data-and-storage/object-storage).
Der vorhandene Django-Adapter nutzt `upload_from_bytes`, `download_as_bytes` und
den zentralen Client mit expliziter Bucket-ID.

Im Replit-Workspace ist das konfigurierte App-Storage-Backend zuständig. Auf dem
eigenen Server bleibt das bestehende `MEDIA_ROOT`-Backend zuständig. Dessen
Medienverzeichnis muss wie bisher persistent eingebunden und gesichert sein.
URLs bleiben mit `/media/` auf der eigenen Domain. Profilbild-Uploads und kompakte
News-Kacheln werden nicht umgestellt.

Alte Base64-Rasterbilder bleiben unverändert in der Datenbank. Nur die vollständige
News-Seite ersetzt sie bei der Ausgabe durch separate, cachebare Bild-URLs. Dieser
Lesepfad schreibt weder Datenbank noch Bildspeicher. Andere historische Bildformate
behalten die bisherige Anzeige im Bildkontext. Die neuen Upload-Limits gelten
nicht nachträglich für diesen Anzeigepfad.

## Optionale, reversible Migration

Die Migration wird **nicht automatisch** ausgeführt. Zuerst Vorschau:

```sh
python manage.py migrate_news_images --club-id 123
```

Optional mit `--news-id 456` auf einen Beitrag begrenzen. Ohne Filter gilt der
Befehl für alle Beiträge. Erst mit ausdrücklichem `--apply` werden Daten geändert:

```sh
python manage.py migrate_news_images --club-id 123 --apply
```

Pro Beitrag werden zuerst alle Dateien geschrieben und bytegenau zurückgelesen.
Danach wird eine ebenfalls verifizierte JSON-Sicherung unter
`news-image-backups/<id>-<zufallswert>.json` gespeichert. Sie enthält die ursprünglichen
Bilddaten und den migrierten Zustand. Erst dann werden die beiden News-JSON-Felder
atomar umgestellt. Die ausgegebenen Sicherungspfade aufbewahren.

Fehlerhafte, übergroße oder nicht mehr zum neuen Upload-Vertrag passende Altbilder
bleiben unverändert; der Befehl meldet betroffene Beitrags-IDs und endet mit einem
Fehlerstatus. Bereits erfolgreich migrierte Beiträge bleiben erfolgreich. Wiederholen
ist sicher: Beiträge ohne Data-URLs werden übersprungen. Es werden keine Originale,
Sicherungen oder Bilddateien gelöscht.

Wiederherstellung, ebenfalls zuerst als Vorschau:

```sh
python manage.py migrate_news_images --restore news-image-backups/456-<zufallswert>.json
python manage.py migrate_news_images --restore news-image-backups/456-<zufallswert>.json --apply
```

Eine Wiederherstellung verweigert das Überschreiben zwischenzeitlich geänderter
Beiträge. Sie löscht keine Dateien und ändert weder Titel noch Verfasser oder Datum.

## Sicherungen nicht öffentlich ausliefern

Der Django-Medienendpunkt blockiert `news-image-backups/` und Traversal-Pfade.
Die mitgelieferte nginx-Vorlage enthält ebenfalls diese Sperre. **Auf bestehenden
Servern die aktualisierte nginx-Konfiguration vor der Migration aktivieren:**

```nginx
location ^~ /media/news-image-backups/ {
    return 404;
}
```

Auch bei sonstigen CDN-/Proxy-Regeln muss dieser Präfix privat bleiben. App Storage
darf nicht durch eine zusätzliche öffentliche Bucket-Freigabe diese Sperre umgehen.
Sicherungen ausschließlich über den Betreiber-Befehl lesen, nicht über News-URLs.