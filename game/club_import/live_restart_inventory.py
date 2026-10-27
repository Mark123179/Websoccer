"""Read-only handoff inventory; never a reset or a database export."""
from collections import Counter

from django.db import connection, transaction
from django.db.models import Q

from game import models as m
from .package_validation import digest
from .runtime import package_mode


def build_inventory():
    # A standalone invocation owns a read-only PostgreSQL snapshot. Callers that
    # already own a transaction (e.g. tests) keep their transaction unchanged.
    owns_transaction = not connection.in_atomic_block
    with transaction.atomic():
        if connection.vendor == "postgresql" and owns_transaction:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        runs = list(m.SourceImportRun.objects.filter(
            source="club_package", status="applied", club__isnull=False,
        ).select_related("club__league").order_by("club_id", "-applied_at", "-pk"))
        latest = {}
        for run in runs:
            latest.setdefault(run.club_id, run)
        club_ids = list(latest)
        players = m.Player.objects.filter(
            Q(club_id__in=club_ids) | Q(owner_club_id__in=club_ids))
        player_ids = players.values("pk")
        clubs = []
        problems = []
        for run in latest.values():
            club = run.club
            # data_sha256 hashes original data.json bytes, not canonical JSON.
            # Those original bytes are not retained in the JSON database column.
            archive_ok = bool(
                isinstance(run.package_data, dict) and run.package_data
                and isinstance(run.manifest, dict) and run.manifest
                and len(run.data_sha256) == 64
                and run.data_sha256 == run.manifest.get("data_sha256"))
            if not archive_ok:
                problems.append(f"Paketarchiv oder Quell-Prüfsummenmetadaten fehlen/weichen ab: TM {club.transfermarkt_id}")
            clubs.append({
                "tm_id": club.transfermarkt_id,
                "name": club.name,
                "league": club.league.name if club.league_id else None,
                "league_playable": club.league.is_playable if club.league_id else None,
                "import_state": club.import_state,
                "source_sha256": run.data_sha256,
                "source_metadata_consistent": archive_ok,
                "stored_package_canonical_sha256": digest(run.package_data),
            })
        # Never output account data, database identifiers/credentials or raw dumps.
        sample = m.Player.objects.filter(transfermarkt_id=796297).first()
        return {
            "format": "WS_LIVE_RESTART_INVENTORY_V1",
            "read_only": True,
            "ready_for_reset": False,
            "package_mode": package_mode(),
            "summary": {
                "applied_import_runs": len(runs),
                "clubs": len(clubs),
                "leagues": dict(sorted(Counter(c["league"] or "Ohne Liga" for c in clubs).items())),
                "players": players.count(),
                "locked_players": players.filter(import_lock=True).count(),
                "market_value_points": m.PlayerMarketValueSnapshot.objects.filter(player_id__in=player_ids).count(),
                "transfer_history_rows": m.PlayerTransferHistory.objects.filter(player_id__in=player_ids).count(),
                "consistent_source_metadata": sum(c["source_metadata_consistent"] for c in clubs),
            },
            "acceptance_sample": None if sample is None else {
                "name": "Jobe Bellingham",
                "tm_id": sample.transfermarkt_id,
                "main_positions": sample.main_positions,
                "secondary_positions": sample.secondary_positions,
                "market_value_points": sample.market_value_snapshots.count(),
                "transfer_history_rows": m.PlayerTransferHistory.objects.filter(player=sample).count(),
            },
            "clubs": sorted(clubs, key=lambda c: (c["league"] or "", c["name"])),
            "source_problems": problems,
            "required_before_reset": [
                "Live-Schreiber pausieren und private vollständige Sicherungen prüfen.",
                "Echte Wiederherstellung auf separater Server-Prüfdatenbank nachweisen.",
                "Aktuelle Live-Reset-Vorschau und Schutzliste separat freigeben.",
                "Vollständige Übernahme einschließlich manueller Nachpflege auf Prüfkopie nachweisen.",
                "Aktuellen Gesamtteststand prüfen; historische grüne Tests reichen nicht.",
            ],
            "limitations": [
                "Dies ist ein Inventar, kein Importpaket und kein Datenbank-Backup.",
                "Konsistente Metadaten sind keine Verifikation der ursprünglichen ZIP-/JSON-Bytes.",
                "Der kanonische JSON-Hash ist nicht die Prüfsumme der ursprünglichen data.json-Datei.",
                "Archivstände belegen nicht, dass manuelle Nachpflege in den Paketen enthalten ist.",
                "Workspace-Nachweise ersetzen keine Prüfung der Live-Datenbank.",
                "Paketmodus, Reset und Import werden durch dieses Kommando niemals ausgeführt.",
            ],
        }
