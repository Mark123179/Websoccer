"""ZIP-Reader für WS_CLUB_IMPORT_V2-Pakete.

Ein Importpaket ist ein ZIP-Archiv mit mindestens zwei Pflichtbestandteilen:
* ``manifest.json`` — Metadaten + Schemaversion + import_ready-Flag
* ``*_master_complete.csv`` — die kanonische Import-CSV (SSOT)

Das Modul ist zustandslos und hat keinen DB-Zugriff. Es liefert den
Master-CSV-Text (UTF-8-sig) an :func:`game.club_import.club_csv_import.import_club_csv`
weiter – genau wie ``open(path, encoding='utf-8-sig').read()``.
"""

import io
import json
import zipfile

from .club_csv_import import ClubImportError

REQUIRED_SCHEMA_VERSION = 'WS_CLUB_IMPORT_V2'


class ZipManifest:
    """Validiertes Manifest eines WS_CLUB_IMPORT_V2-ZIPs."""

    def __init__(self, data: dict):
        self.schema_version: str = data.get('schema_version', '')
        self.club: str = data.get('club', '')
        self.season: str = data.get('season', '')
        self.player_count: int = data.get('player_count', 0)
        self.import_ready: bool = bool(data.get('import_ready', False))
        self.package_name: str = data.get('package_name', '')
        self.source_as_of: str = data.get('source_as_of', '')
        self._raw = data


def _find_manifest_path(namelist: list[str]) -> str | None:
    """Gibt den ZIP-internen Pfad zu manifest.json zurück (auch in Unterordnern)."""
    for name in namelist:
        if name.endswith('manifest.json') and not name.startswith('__MACOSX'):
            return name
    return None


def _find_master_csv_path(namelist: list[str]) -> str | None:
    """Gibt den ZIP-internen Pfad zur *_master_complete.csv zurück."""
    for name in namelist:
        basename = name.rsplit('/', 1)[-1]
        if basename.endswith('_master_complete.csv') and not name.startswith('__MACOSX'):
            return name
    return None


def read_zip(path_or_bytes) -> tuple[str, ZipManifest]:
    """Öffnet ein WS_CLUB_IMPORT_V2-ZIP und gibt ``(csv_text, manifest)`` zurück.

    Args:
        path_or_bytes: Dateipfad (str/Path) oder Bytes-Objekt des ZIPs.

    Returns:
        ``(csv_text, manifest)`` — csv_text ist der Master-CSV-Inhalt als
        UTF-8-String (BOM entfernt), manifest ist ein :class:`ZipManifest`.

    Raises:
        ClubImportError: Ungültiges Schema, fehlendes Manifest, import_ready=false,
            fehlende Master-CSV oder beschädigtes ZIP.
    """
    try:
        if isinstance(path_or_bytes, (bytes, bytearray)):
            zf = zipfile.ZipFile(io.BytesIO(path_or_bytes))
        else:
            zf = zipfile.ZipFile(path_or_bytes)
    except zipfile.BadZipFile as exc:
        raise ClubImportError(f'Kein gültiges ZIP-Archiv: {exc}')

    with zf:
        namelist = zf.namelist()

        manifest_path = _find_manifest_path(namelist)
        if manifest_path is None:
            raise ClubImportError(
                'ZIP enthält keine manifest.json – kein WS_CLUB_IMPORT_V2-Paket.'
            )

        try:
            raw_manifest = zf.read(manifest_path).decode('utf-8-sig')
            manifest_data = json.loads(raw_manifest)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ClubImportError(f'manifest.json konnte nicht gelesen werden: {exc}')

        schema = manifest_data.get('schema_version', '')
        if schema != REQUIRED_SCHEMA_VERSION:
            raise ClubImportError(
                f'Falsches Schema: erwartet „{REQUIRED_SCHEMA_VERSION}", '
                f'gefunden „{schema}".'
            )

        if not manifest_data.get('import_ready', False):
            raise ClubImportError(
                'Paket ist nicht importbereit (import_ready=false im Manifest).'
            )

        master_path = _find_master_csv_path(namelist)
        if master_path is None:
            raise ClubImportError(
                'ZIP enthält keine *_master_complete.csv – Master-CSV fehlt.'
            )

        try:
            raw_csv = zf.read(master_path)
            try:
                csv_text = raw_csv.decode('utf-8-sig')
            except UnicodeDecodeError:
                csv_text = raw_csv.decode('latin-1')
        except Exception as exc:
            raise ClubImportError(f'Master-CSV konnte nicht gelesen werden: {exc}')

    return csv_text, ZipManifest(manifest_data)
