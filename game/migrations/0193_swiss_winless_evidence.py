"""Correct only the two existing Swiss SEED records, never reimport clubs."""
from django.db import migrations
from django.utils import timezone

from game.club_import.swiss_winless_20261027 import RECORDS


def apply_evidence(apps, schema_editor):
    Record = apps.get_model("game", "ClubRecord")
    Issue = apps.get_model("game", "ImportIssue")
    alias = schema_editor.connection.alias
    for tm, fact in RECORDS.items():
        rows = Record.objects.using(alias).filter(
            club__transfermarkt_id=tm, record_key="longest_winless", source="SEED",
        )
        row = rows.select_for_update().first()
        # Empty/new workspaces must not acquire clubs or invented history.
        if row is None:
            continue
        if row.value_numeric == 16 and row.evidence_status == "belegt":
            # A subsequent manual correction must not be overwritten on replay.
            continue
        if row.value_numeric is not None or row.evidence_status != "nicht_belegt":
            raise RuntimeError(
                f"Swiss record TM {tm} differs from the approved open state; "
                "review it before applying this correction."
            )
        rows.update(
            value_numeric=fact["value_numeric"], value_display=fact["value_display"],
            period_from=fact["period_from"], period_to=fact["period_to"],
            season=fact["season"], competition=fact["competition"],
            context_line=fact["context"], evidence=fact["sources"],
            evidence_status="belegt", basis="all_competitive",
        )
        Issue.objects.using(alias).filter(
            club_id=row.club_id, entity="record", entity_ref="longest_winless",
            field="records.longest_winless", severity="info",
            resolution_status="open", note__contains="Ersatzwert ohne alte",
        ).update(resolution_status="resolved", resolved_at=timezone.now())


class Migration(migrations.Migration):
    atomic = True
    dependencies = [("game", "0192_player_identity_audit_snapshot")]
    # Reversal must never reactivate the rejected Intertoto records.
    operations = [migrations.RunPython(apply_evidence, migrations.RunPython.noop)]
