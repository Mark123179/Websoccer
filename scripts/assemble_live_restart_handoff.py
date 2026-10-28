"""Build + verify the combined handoff, confined to new isolated SQLite files.

Run after a fresh read-only live_restart_package export. This script never
connects to the workspace database and has no production/import/reset mode.
"""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-package", required=True)
    parser.add_argument("--swiss-source", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--resume-assembly", action="store_true",
                        help="Nur bereits isoliert importierten Zwischenstand weiterprüfen.")
    args = parser.parse_args()
    # Force safe settings before any Django import/setup. The paths below are
    # selected explicitly, never from DATABASE_URL or production settings.
    os.environ["DJANGO_SETTINGS_MODULE"] = "core.live_restart_verify_settings"
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection, transaction
    from game import models as m
    from game.club_import.restart_export import (
        HandoffError, build_package, read_package, write_package, canonical, sha,
    )
    from game.club_import.restart_schema import FIELDS, MODELS
    from game.club_import.restart_verify import replay
    from game.club_import.restart_baseline import protect_baseline
    from scripts import import_swiss_packages as swiss

    root = Path(args.output_dir).resolve()
    allowed = (Path(settings.BASE_DIR) / "generated-artifacts" / "live-restart").resolve()
    if allowed not in root.parents or (root.exists() and not args.resume_assembly):
        raise HandoffError("Neues Unterverzeichnis unter generated-artifacts/live-restart erforderlich.")
    base = read_package(args.base_package)
    root.mkdir(parents=True, exist_ok=args.resume_assembly)

    def save(name, value):
        (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def fresh_database(name):
        connection.close()
        connection.settings_dict["NAME"] = root / name
        if Path(connection.settings_dict["NAME"]).exists():
            raise HandoffError("Prüfdatei existiert bereits; kein Überschreiben.")
        call_command("migrate", run_syncdb=True, interactive=False, verbosity=0)

    if args.resume_assembly:
        previous = json.loads((root / "base-parity.json").read_text())
        if {k: v["expected"] for k, v in previous["table_comparisons"].items()} != base["parity"]:
            raise HandoffError("Fortsetzung gehört nicht zu diesem Basis-Snapshot.")
        connection.close()
        connection.settings_dict["NAME"] = root / "assembly.sqlite3"
        provenance = json.loads((root / "swiss-source-projection.json").read_text())
        import hashlib
        if hashlib.sha256(Path(args.swiss_source).read_bytes()).hexdigest() != swiss.SOURCE_SHA:
            raise HandoffError("Schweizer Quelle stimmt nicht.")
        paths = sorted((root / "swiss-projections").glob("*.zip"))
        swiss.verify(m.League.objects.get(name="Super League", country="Schweiz"), paths)
    else:
        fresh_database("assembly.sqlite3")
        save("base-parity.json", replay(base))
    # Preserve evidence for every baseline row in the destination. These are
    # local scratch IDs only; no workspace IDs are used or put in the bundle.
    before = {
        name: {obj.pk: {
            f: getattr(obj, model._meta.get_field(f).attname) for f in FIELDS[name]
        } for obj in model.objects.all()}
        for name, model in MODELS.items()
    }
    if not args.resume_assembly:
        paths, provenance = swiss.prepare(args.swiss_source, root / "swiss-projections")
        with transaction.atomic():
            league = m.League.objects.create(
                name="Super League", country="Schweiz", level=1,
                max_teams=12, is_playable=False)
            report = swiss.import_batch(
                paths, swiss.OWNER_EXCEPTIONS, apply=True, target_league_id=league.pk,
                approved_club_countries={163: "Liechtenstein"})
            swiss.verify(league, paths)
        save("swiss-source-projection.json", provenance)
    # The canonical batch report contains scratch IDs. Keep the raw report
    # local, not in the transport. Its protected-state/exact-replay checks ran.
        save("swiss-isolated-import.json", report)
    changes = {}
    for name, model in MODELS.items():
        actual = {obj.pk: obj for obj in model.objects.all()}
        entries = []
        for pk, old in before[name].items():
            if pk not in actual:
                entries.append({"deleted": True, "old_content_sha256": sha(old)})
                continue
            changed = {
                field: {
                    "before": json.loads(canonical(value)),
                    "after": json.loads(canonical(getattr(
                        actual[pk], model._meta.get_field(field).attname))),
                }
                for field, value in old.items()
                if value != getattr(actual[pk], model._meta.get_field(field).attname)
            }
            if changed:
                entries.append({
                    "identity": (
                        actual[pk].transfermarkt_id if name == "Player"
                        else sha(old)),
                    "fields": changed,
                })
        if entries:
            changes[name] = entries
    save("baseline-staging-changes.json", changes)
    swiss_tms = list(m.Club.objects.filter(league__country="Schweiz").values_list(
        "transfermarkt_id", flat=True))
    baseline_protection = protect_baseline(base, swiss_tms)
    save("baseline-preservation.json", baseline_protection)
    swiss.verify(m.League.objects.get(name="Super League", country="Schweiz"), paths)
    combined = build_package()
    if combined["blockers"]:
        raise HandoffError("Kombinierter Stand bleibt gesperrt: " + "; ".join(combined["blockers"]))
    if len(combined["imported_clubs"]) != len(base["imported_clubs"]) + 12:
        raise HandoffError("Vereinsumfang stimmt nicht mit Basis plus Schweiz überein.")
    combined["assembly"] = {
        "source": "current_workspace_snapshot_plus_approved_swiss_projection",
        "base_table_parity": base["parity"],
        "swiss_original_sha256": swiss.SOURCE_SHA,
        "workspace_switzerland_present": False,
        "switzerland_added_only_in_isolated_copy": True,
        "swiss_projection": provenance,
        "baseline_preservation": baseline_protection,
    }
    output = root / "complete-current-state.zip"
    checksum = write_package(output, combined)
    fresh_database("verification.sqlite3")
    verified = replay(read_package(output))
    verified["package_sha256"] = checksum
    verified["package_file"] = output.name
    save("complete-parity.json", verified)
    save("complete-manifest.json", {
        key: value for key, value in combined.items()
        if key not in ("tables", "source_archives")
    })
    print(json.dumps({
        "package": str(output), "sha256": checksum,
        "inventory": combined["inventory"]["summary"],
        "all_tables_identical": verified["all_tables_identical"],
        "blockers": combined["blockers"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
