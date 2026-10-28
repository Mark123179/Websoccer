"""Protect CURRENT baseline facts from an older, overlapping Swiss delivery.

Only intended for the isolated assembly, never the workspace or production.
The replay's independently generated destination IDs are used locally; no
workspace PK is read from or written to a handoff package.
"""
import json

from django.db import connection, transaction

from .restart_export import HandoffError, canonical, sha
from .restart_schema import FIELDS, MODELS
from .restart_verify import assert_isolated


def replay_keys(package):
    keys = {}
    pk = 10_000_000
    for name in MODELS:
        for row in package["tables"][name]:
            pk += 1
            keys[name, row["key"]] = pk
    return keys


def baseline_values(package, keys):
    for name, model in MODELS.items():
        for row in package["tables"][name]:
            data = {}
            for field, value in row["values"].items():
                f = model._meta.get_field(field)
                if f.is_relation and value is not None:
                    value = keys[f.related_model.__name__, value]
                data[f.attname] = value
            yield name, keys[name, row["key"]], model(**data), row["key"]


def protect_baseline(package, new_club_tms):
    assert_isolated(require_empty=False)
    from game import models as m
    from .package_service import link_references
    keys = replay_keys(package)
    pids = [pk for (name, _), pk in keys.items() if name == "Player"]
    with transaction.atomic():
        # The older source may have deleted/recreated current ratings. Preserve
        # the current snapshot wholesale, including NULLs and all attributes.
        with connection.cursor() as cursor:
            rating_table = connection.ops.quote_name(m.PlayerSourceRating._meta.db_table)
            for start in range(0, len(pids), 500):
                part = pids[start:start + 500]
                cursor.execute(
                    f"DELETE FROM {rating_table} WHERE player_id IN (" +
                    ", ".join(["%s"] * len(part)) + ")", part)
            for name, pk, obj, _ in baseline_values(package, keys):
                model = MODELS[name]
                fs = [model._meta.get_field(field) for field in FIELDS[name]]
                values = [f.get_db_prep_save(getattr(obj, f.attname), connection) for f in fs]
                table = connection.ops.quote_name(model._meta.db_table)
                if name == "PlayerSourceRating":
                    cursor.execute(
                        f"INSERT INTO {table} (id, " +
                        ", ".join(connection.ops.quote_name(f.column) for f in fs) +
                        ") VALUES (" + ", ".join(["%s"] * (len(fs) + 1)) + ")",
                        [pk, *values])
                else:
                    cursor.execute(
                        f"UPDATE {table} SET " +
                        ", ".join(f"{connection.ops.quote_name(f.column)} = %s" for f in fs) +
                        " WHERE id = %s", [*values, pk])
                    if cursor.rowcount != 1:
                        raise HandoffError(f"Baseline-Zeile fehlt nach Schweizer Ergänzung: {name}")
        # Only resolve previously missing clubs through their already stored TM
        # identities. Do not reapply source ratings, positions or squad choices.
        for club in m.Club.objects.filter(transfermarkt_id__in=new_club_tms):
            link_references(club)
        # Convert an old scratch-PK-bearing source note to a source-only note.
        for issue in m.ImportIssue.objects.filter(subkey="approved-existing-owner"):
            evidence = issue.external_reference
            if isinstance(evidence, dict) and isinstance(evidence.get("preserved_owner"), dict):
                evidence["preserved_owner"].pop("owner_club_id", None)
                issue.external_reference = evidence
                issue.save(update_fields=["external_reference"])
        connection.check_constraints()
        return verify_baseline(package, keys, new_club_tms)


def verify_baseline(package, keys, new_club_tms):
    from game import models as m
    clubs = dict(m.Club.objects.values_list("pk", "transfermarkt_id"))
    new_tms = set(new_club_tms)
    rows = {
        name: {obj.pk: obj for obj in model.objects.all()}
        for name, model in MODELS.items()
    }
    reference_fields = {
        "Player": {
            "club": "loan_club_tm_id", "owner_club": "owner_club_tm_id",
            "loan_club": "loan_club_tm_id",
        },
        "PlayerMarketValueSnapshot": {"club": "club_tm_id"},
        "PlayerTransferHistory": {"from_club": "from_tm_id", "to_club": "to_tm_id"},
        "ClubRecord": {"opponent_club": "opponent_tm_id"},
    }
    counts = {}
    allowed = []
    for name, pk, old, identity in baseline_values(package, keys):
        new = rows[name].get(pk)
        if new is None:
            raise HandoffError(f"Baseline-Zeile fehlt: {name}")
        counts[name] = counts.get(name, 0) + 1
        for field in FIELDS[name]:
            f = MODELS[name]._meta.get_field(field)
            before, after = getattr(old, f.attname), getattr(new, f.attname)
            # Convert ORM/raw incoming dates & decimals consistently.
            before = f.to_python(before) if not f.is_relation else before
            after = f.to_python(after) if not f.is_relation else after
            if before == after:
                continue
            source_field = reference_fields.get(name, {}).get(field)
            good = (before is None and source_field is not None
                    and clubs.get(after) in new_tms
                    and getattr(old, source_field) == clubs.get(after))
            if name == "Player":
                # At the borrower's club a newly resolved loan changes its
                # display-side state, not its approved owner or end date.
                if field == "loan_status":
                    good = before == "loaned_out" and after == "loaned_in" and clubs.get(new.club_id) in new_tms
                elif field == "pool_status":
                    good = (before == "unavailable" and after in ("scoutable", "unavailable")
                            and clubs.get(new.club_id) in new_tms)
                elif field == "loan_partner_club":
                    good = (before is None and new.loan_status == "loaned_in"
                            and after == new.owner_club_id and
                            (clubs.get(new.club_id) in new_tms or clubs.get(new.owner_club_id) in new_tms))
            if not good:
                raise HandoffError(f"Unerlaubte Baseline-Abweichung: {identity}.{field}")
            allowed.append({
                "row": identity, "field": field,
                "before": None if f.is_relation else json.loads(canonical(before)),
                "after": {"club_tm": clubs[after]} if f.is_relation else json.loads(canonical(after)),
            })
    return {
        "all_current_baseline_facts_preserved": True,
        "checked_rows": counts,
        "allowed_source_identity_resolutions": allowed,
        "allowed_source_identity_resolutions_sha256": sha(allowed),
        "rule": "Nur zuvor fehlende Quellvereins-Verknüpfungen und deren Leihanzeige aufgelöst.",
    }
