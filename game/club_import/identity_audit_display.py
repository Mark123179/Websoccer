"""Club projection of saved reports: select entire components, never graph nodes."""
import json

from django.core.paginator import Paginator

from game.models import Club, PlayerIdentityAuditSnapshot


def finding_club_ids(finding):
    clubs = {
        player.get(field)
        for player in finding["players"]
        for field in ("club_id", "owner_club_id", "loan_club_id")
    }
    clubs.update(record["club_id"] for record in finding["record_references"])
    return clubs - {None}


def club_identity_audit_context(club_id, page_number):
    snapshot = PlayerIdentityAuditSnapshot.objects.filter(pk=1).first()
    if snapshot is None:
        return {"identity_snapshot": None}
    report = snapshot.report
    findings = [
        dict(finding, report_number=index)
        for index, finding in enumerate(report["findings"], 1)
        if club_id in finding_club_ids(finding)
    ]
    page = Paginator(findings, 20).get_page(page_number)
    club_ids = {pk for finding in page for pk in finding_club_ids(finding)}
    # Do not use visible_clubs(): foreign/hidden clubs are relevant evidence too.
    names = dict(Club.objects.filter(pk__in=club_ids).values_list("pk", "name"))
    for finding in page:
        finding["clubs"] = [
            {"id": pk, "name": names.get(pk, f"Verein #{pk}")}
            for pk in sorted(finding_club_ids(finding))
        ]
        for key in ("problems", "evidence", "canonical_rows", "record_references"):
            finding[key + "_json"] = json.dumps(finding[key], ensure_ascii=False, indent=2)
    return {
        "identity_snapshot": snapshot,
        "identity_summary": report["summary"],
        "identity_policy": report["policy"],
        "identity_page": page,
    }
