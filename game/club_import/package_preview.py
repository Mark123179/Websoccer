"""Read-only package comparison. No draft rows and no strength writes."""
from copy import deepcopy
from collections import Counter
import hashlib
import json
from pathlib import Path
from django.conf import settings
from django.db.models import Q
from game import models as m
from .package_validation import read_package
from .issue_lifecycle import candidates, plan
from .runtime import image_check_enabled


def image_gaps(data):
    if not image_check_enabled():
        return []
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
                changes.append(dict(player=target.get("display_name", club.name),
                                    entity_ref=issue.entity_ref, field=issue.field,
                                    old=issue.manual_value, new=incoming["value"]))
            continue
        if parts[0] == "ids":
            if incoming.get("value") is None:
                cursor[parts[-1]] = dict(incoming, value=issue.manual_value, status="von_hand")
            elif incoming["value"] != issue.manual_value:
                changes.append(dict(player=target.get("display_name", club.name),
                    entity_ref=issue.entity_ref, field=issue.field,
                    old=issue.manual_value, new=incoming["value"]))
        elif incoming is None:
            cursor[parts[-1]] = issue.manual_value
        elif incoming != issue.manual_value:
            changes.append(dict(player=target.get("display_name", club.name),
                entity_ref=issue.entity_ref, field=issue.field, old=issue.manual_value, new=incoming))
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


def live_loan_preview(data, original, club, league, historical_links):
    """Project the service's live-loan branches, without locks or writes."""
    from .package_service import identity, assert_live_loan_compatible, league_started
    from .package_validation import PackageError

    if league.is_playable:
        return [], []
    owner_tm = data["club"]["ids"]["tm"]["value"]
    historical = {link["tm"]: link for link in historical_links}
    originals = {p["ids"]["tm"]["value"]: p for p in original["players"]}
    protected, states, included = [], [], set()

    def preserve(player, *, tm=None, omitted=False):
        if tm is None:
            tm = player.transfermarkt_id
        protected.append(dict(
            player_id=player.pk, tm=tm, name=player.full_name,
            owner=player.owner_club.name if player.owner_club_id else data["club"]["name"],
            owner_tm=player.owner_club_tm_id,
            borrower=player.club.name, borrower_tm=player.club.transfermarkt_id,
            loan_until=player.loan_until, omitted=omitted,
            source_json=json.dumps(originals[tm], ensure_ascii=False, indent=2)
                        if not omitted else "",
        ))
        states.append(dict(player=m.Player.objects.filter(pk=player.pk).values().get(),
                           borrower=m.Club.objects.filter(pk=player.club_id).values().get()))

    for pdata in data["players"]:
        tm = pdata["ids"]["tm"]["value"]
        try:
            player = identity(pdata["ids"], m.Player, lock=False)
        except PackageError:
            player = m.Player.objects.filter(transfermarkt_id=tm).first()
            if player and player.club_id and player.club.league.is_playable:
                raise PackageError("Conflicting identities for an active first-league player.")
            continue
        link = historical.get(tm)
        if link and link["player_id"]:
            player = m.Player.objects.get(pk=link["player_id"])
        if player:
            included.add(player.pk)
        if player and player.club_id and player.club.league.is_playable:
            assert_live_loan_compatible(player, pdata, owner_tm)
            preserve(player, tm=tm)

    if club and not league_started(league):
        missing = m.Player.objects.filter(Q(club=club) | Q(owner_club=club)).exclude(
            pk__in=included).select_related("club__league", "owner_club").order_by("pk")
        for player in missing:
            if player.club_id and player.club.league.is_playable:
                preserve(player, omitted=True)
    return protected, states


def preview_package(raw, league):
    manifest, data = read_package(raw)
    club = m.Club.objects.filter(transfermarkt_id=manifest["club"]["tm_id"]).first()
    effective, manual_changes = preserved_manual(data, club)
    from .historical_identity import historical_plan
    historical_links = historical_plan(effective)
    live_loans, live_states = live_loan_preview(effective, data, club, league, historical_links)
    protected_tms = {p["tm"] for p in live_loans}
    protected_refs = {f"tm:{tm}" for tm in protected_tms}
    rows = candidates(effective, club)
    _, _, balance = plan(club, rows)
    changes = [change for change in manual_changes if change.get("entity_ref") not in protected_refs]
    last = m.SourceImportRun.objects.filter(club=club, status="applied").order_by("-applied_at", "-pk").first() if club else None
    previous = {p["ids"]["tm"]["value"]: p for p in last.package_data["players"]} if last else {}
    title_changes = []
    if last:
        old_titles = {(t["competition"]["name"], t["season"]): t for t in last.package_data["titles"]}
        for title in data["titles"]:
            old = old_titles.get((title["competition"]["name"], title["season"]))
            if old and old["competition"]["category"] != title["competition"]["category"]:
                title_changes.append(dict(competition=title["competition"]["name"], season=title["season"],
                    old=old["competition"]["category"], new=title["competition"]["category"]))
    for player in data["players"]:
        if player["ids"]["tm"]["value"] in protected_tms:
            continue
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
    review = list(m.Player.objects.filter(owner_club=club)
                  .exclude(transfermarkt_id__in=incoming)
                  .exclude(pk__in=[p["player_id"] for p in live_loans])
                  .values_list("display_name", flat=True)) if club else []
    new_strength_players = [p["display_name"] for p in data["players"] if
        p["ids"]["tm"]["value"] not in protected_tms
        and p["ids"]["tm"]["value"] in previous
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
    state["historical_links"] = historical_links
    state["live_loans"] = live_states
    state["image_check_enabled"] = image_check_enabled()
    state["images"] = image_gaps(data)
    state["title_changes"] = title_changes
    if club:
        state["issues"] = list(m.ImportIssue.objects.filter(club=club).order_by("pk").values())
        state["club"] = list(m.Club.objects.filter(pk=club.pk).values())
        state["players"] = list(m.Player.objects.filter(owner_club=club).order_by("pk").values())
        state["ids"] = list(m.PlayerExternalId.objects.filter(player__owner_club=club).order_by("pk").values())
        state["ratings"] = list(m.PlayerSourceRating.objects.filter(player__owner_club=club).order_by("pk").values())
        state["seasons"] = list(m.LeagueSeasonState.objects.filter(league=league).order_by("pk").values())
        state["titles"] = list(m.ClubTrophyEntry.objects.filter(club=club).order_by("pk").values())
    guard = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()
    return dict(manifest=manifest, data=display_data, changes=changes, title_changes=title_changes, issue_balance=balance,
        image_check_enabled=image_check_enabled(),
        missing_images=image_gaps(data), players_to_review=review,
        new_strengths=new_strength, new_strength_players=new_strength_players, guard=guard,
        historical_links=historical_links,
        protected_live_loans=live_loans,
        baseline=last.data_sha256 if last else "",
        effective=effective)
