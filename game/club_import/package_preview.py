"""Read-only package comparison. No draft rows and no strength writes."""
from copy import deepcopy
from collections import Counter
import hashlib
import json
from pathlib import Path
from django.conf import settings
from game import models as m
from .package_validation import read_package
from .issue_lifecycle import candidates, plan


def image_gaps(data):
    from game.asset_urls import assets_root
    root = Path(assets_root())
    checks = []
    entities = [("club", f"tm:{data['club']['ids']['tm']['value']}",
                 data["club"]["ids"]["fmi"]["value"], "clubs/logos")]
    entities += [("player", f"tm:{p['ids']['tm']['value']}", p["ids"]["fmi"]["value"],
                  "players") for p in data["players"]]
    entities += [("person", p["ref"], p.get("fmi_id"), "players")
                 for p in data["persons"]]
    for kind, ref, fmi, folder in entities:
        filename = f"{fmi}_club.png" if folder == "clubs/logos" else f"face_{fmi}.png"
        path = root / folder / filename if fmi else None
        if path and folder == "players":
            path = next((path.with_suffix("." + ext) for ext in ("png", "jpg", "jpeg", "webp")
                         if path.with_suffix("." + ext).is_file()), path)
        if path is None or not path.is_file():
            checks.append(dict(entity=kind, ref=ref, field="image", severity="info",
                note="Bild fehlt: " + (str(path.relative_to(root)) if path else "keine FM-ID")))
    return checks


def preserved_manual(data, club):
    result = deepcopy(data)
    changes = []
    if not club:
        return result, changes
    by_tm = {f"tm:{p['ids']['tm']['value']}": p for p in result["players"]}
    for issue in m.ImportIssue.objects.filter(club=club, manual_value__isnull=False):
        if issue.entity == "club_reference" and issue.field == "tm_id":
            refs = [p.get("club") for player in result["players"] for p in player["market_values"]]
            refs += [fact.get(side) for player in result["players"]
                     for fact in player["transfers"] for side in ("from", "to")]
            refs += [fact.get("opponent") for fact in result["records"]]
            supplied = set()
            for ref in refs:
                if ref and ref.get("name") == issue.entity_ref:
                    if ref.get("tm_id") is None:
                        ref.update(tm_id=issue.manual_value, status="von_hand")
                    elif ref["tm_id"] != issue.manual_value:
                        supplied.add(ref["tm_id"])
            for value in supplied:
                changes.append(dict(player=issue.entity_ref, field="tm_id",
                                    old=issue.manual_value, new=value))
            continue
        target = by_tm.get(issue.entity_ref) if issue.entity == "player" else (
            result["stadium"] if issue.entity == "club" and issue.field.startswith(("stands.", "totals."))
            else result["club"] if issue.entity == "club" else None)
        if target is None:
            continue
        parts = issue.field.split(".")
        cursor = target
        for part in parts[:-1]:
            if not isinstance(cursor, dict) or part not in cursor:
                cursor = None
                break
            cursor = cursor[part]
        if cursor is None or parts[-1] not in cursor:
            continue
        incoming = cursor[parts[-1]]
        if isinstance(incoming, dict) and "value" in incoming and parts[0] != "ids":
            if incoming["value"] is None:
                cursor[parts[-1]] = dict(incoming, value=issue.manual_value)
            elif incoming["value"] != issue.manual_value:
                changes.append(dict(player=club.name, field=issue.field,
                                    old=issue.manual_value, new=incoming["value"]))
            continue
        if parts[0] == "ids":
            if incoming.get("value") is None:
                cursor[parts[-1]] = dict(incoming, value=issue.manual_value, status="von_hand")
            elif incoming["value"] != issue.manual_value:
                changes.append(dict(player=target.get("display_name", club.name),
                    field=issue.field, old=issue.manual_value, new=incoming["value"]))
        elif incoming is None:
            cursor[parts[-1]] = issue.manual_value
        elif incoming != issue.manual_value:
            changes.append(dict(player=target.get("display_name", club.name),
                field=issue.field, old=issue.manual_value, new=incoming))
    return result, changes


def clear_superseded_manual(data, club):
    """A supplied source value retires the old manual override."""
    by_tm = {f"tm:{p['ids']['tm']['value']}": p for p in data["players"]}
    for issue in m.ImportIssue.objects.filter(club=club, manual_value__isnull=False):
        if issue.entity == "club_reference":
            refs = [point.get("club") for p in data["players"] for point in p["market_values"]]
            refs += [fact.get(side) for p in data["players"] for fact in p["transfers"] for side in ("from", "to")]
            refs += [fact.get("opponent") for fact in data["records"]]
            supplied = any(ref and ref.get("name") == issue.entity_ref and ref.get("tm_id") is not None for ref in refs)
        else:
            target = by_tm.get(issue.entity_ref) if issue.entity == "player" else (
                data["stadium"] if issue.field.startswith(("stands.", "totals.")) else data["club"])
            for part in issue.field.split("."):
                target = target.get(part) if isinstance(target, dict) else None
            if isinstance(target, dict):
                target = target.get("value")
            supplied = target is not None
        if supplied:
            issue.manual_value = None
            issue.save(update_fields=["manual_value"])


def preview_package(raw, league):
    manifest, data = read_package(raw)
    club = m.Club.objects.filter(transfermarkt_id=manifest["club"]["tm_id"]).first()
    effective, manual_changes = preserved_manual(data, club)
    rows = candidates(effective, club)
    _, _, balance = plan(club, rows)
    changes = list(manual_changes)
    last = m.SourceImportRun.objects.filter(club=club, status="applied").order_by("-applied_at", "-pk").first() if club else None
    previous = {p["ids"]["tm"]["value"]: p for p in last.package_data["players"]} if last else {}
    for player in data["players"]:
        old = previous.get(player["ids"]["tm"]["value"])
        if old:
            for provider in ("fminside", "cmtracker"):
                before = old["ratings"].get(provider) or {}
                after = player["ratings"].get(provider) or {}
                for field in ("rating", "potential"):
                    if before.get(field) != after.get(field):
                        changes.append(dict(player=player["display_name"],
                            field=f"ratings.{provider}.{field}", old=before.get(field), new=after.get(field)))
    incoming = {p["ids"]["tm"]["value"] for p in data["players"]}
    review = list(m.Player.objects.filter(owner_club=club).exclude(transfermarkt_id__in=incoming)
                  .values_list("display_name", flat=True)) if club else []
    new_strength_players = [p["display_name"] for p in data["players"] if
        p["ids"]["tm"]["value"] in previous
        and not any((previous[p["ids"]["tm"]["value"]]["ratings"].get(s) or {}).get("potential") is not None
                    for s in ("fminside", "cmtracker"))
        and any((p["ratings"].get(s) or {}).get("potential") is not None for s in ("fminside", "cmtracker"))
        ]
    new_strength = len(new_strength_players)
    severity_counts = Counter(g["severity"] for g in rows)
    display_data = dict(data, squad_counts=dict(first=manifest["counts"]["first_team"],
        u21=manifest["counts"]["u21"]), loan_count=manifest["counts"]["loaned_in"] +
        manifest["counts"]["loaned_out"] + manifest["counts"].get("u21_loaned_out", 0),
        gaps_by_severity=[dict(label=label, severity=label, count=count)
                          for label, count in sorted(severity_counts.items())])
    from .package_service import league_started
    state = dict(league=(league.pk, league.is_playable, league_started(league)),
                 package=last.data_sha256 if last else "")
    state["plan"] = rows
    state["images"] = image_gaps(data)
    if club:
        state["issues"] = list(m.ImportIssue.objects.filter(club=club).order_by("pk").values())
        state["club"] = list(m.Club.objects.filter(pk=club.pk).values())
        state["players"] = list(m.Player.objects.filter(owner_club=club).order_by("pk").values())
        state["ids"] = list(m.PlayerExternalId.objects.filter(player__owner_club=club).order_by("pk").values())
        state["ratings"] = list(m.PlayerSourceRating.objects.filter(player__owner_club=club).order_by("pk").values())
        state["seasons"] = list(m.LeagueSeasonState.objects.filter(league=league).order_by("pk").values())
    guard = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()
    return dict(manifest=manifest, data=display_data, changes=changes, issue_balance=balance,
        missing_images=image_gaps(data), players_to_review=review,
        new_strengths=new_strength, new_strength_players=new_strength_players, guard=guard,
        baseline=last.data_sha256 if last else "",
        effective=effective)
