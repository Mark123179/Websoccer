---
name: Object-Storage Bucket-ID Pflicht
description: Replit Object Storage braucht die Bucket-ID explizit aus dem Secret; Client() ohne Argument crasht, stille Fallbacks verschleiern das.
---

# Object Storage: Client() nie direkt instanziieren

**Regel:** Media-Uploads laufen im Replit-Dev über den Object-Storage-Bucket, auf dem
Self-Hosted-Server über das lokale Filesystem (gesteuert via `USE_REPLIT_OBJECT_STORAGE`,
Default = Replit-Erkennung). Für Bucket-Zugriffe IMMER den zentralen Helper
`game.object_storage_backend.get_client()` nutzen — nie `replit.object_storage.Client()`
direkt.

**Why:** `Client()` ohne Argument sucht den Default-Bucket über die `.replit`-Sektion,
die in diesem Workspace nicht existiert → `DefaultBucketError` bei JEDEM Upload/Download.
Die Bucket-ID liegt stattdessen im Secret `DEFAULT_OBJECT_STORAGE_BUCKET_ID` und muss als
`Client(bucket_id=...)` übergeben werden. Avatar-Pfade hatten den Crash mit
`try/except: pass` verschluckt und still ins lokale Filesystem geschrieben — der kaputte
Bucket fiel deshalb lange nicht auf; erst der ungeschützte Hero-Upload der Show-Auktion
machte ihn sichtbar.

**How to apply:** Bei jedem neuen Feature mit Datei-Upload/-Download (ImageField,
Media-Serving, Cleanup-Commands) den zentralen Helper nutzen statt eines eigenen
Clients. Stille `except: pass` um Storage-Aufrufe vermeiden — lieber Warnung/Fehler
sichtbar machen, sonst landen Dateien unbemerkt im falschen Storage. /media/-Serving
muss bei Bucket-Miss auf MEDIA_ROOT zurückfallen (Altbestand aus der Kaputt-Phase),
404 erst wenn beide Quellen leer sind.
