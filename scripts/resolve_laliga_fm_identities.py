"""Apply only the three DOB-confirmed Workspace FM identity corrections.

Run after the original LaLiga quarantine import. Default: transaction rollback.
No web scraping, whole-roster imports, or birthday-conflict exceptions.
"""
import argparse
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re
from types import SimpleNamespace

from scripts.import_additional_club_packages import (
    fingerprint, m, protected_queries, transaction,
)
from scripts.import_laliga_packages import OUTPUT, QUARANTINE, SOURCE, SOURCE_SHA
from game.club_import.issue_lifecycle import refresh_lock
from game.club_import.package_service import attributes, digest, league_started, source, sync_ids
from game.club_import.package_validation import PackageError
from game.strength_service import compute_strength_for_player
from django.db.models import Q
from django.utils import timezone


CONFIRMED = {
    1342235: (2000395283, "2007-03-10", "anxo-rodriguez"),
    1451988: (2000395286, "2008-08-27", "noah"),
    1064403: (2000374246, "2005-09-15", "alvaro-garcia"),
}
CHECKED = date(2026, 10, 27)


def require(condition, message):
    if not condition:
        raise PackageError(message)


def blocks():
    import hashlib
    require(hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA,
            "Original delivery changed.")
    provenance = json.loads((OUTPUT / "provenance.json").read_text())
    evidence = json.loads((OUTPUT / "fm-identity-research.json").read_text())
    result = {}
    for tm, (uid, dob, slug) in CONFIRMED.items():
        proof = evidence["noah"][1] if tm == 1451988 else next(
            p for p in evidence["sortitoutsi"] if f"/{uid}/" in p["url"])
        require(f"ID {uid}" in proof["markdown"] and f"DOB{dob}" in proof["markdown"],
                f"UID/DOB proof missing for TM {tm}.")
        if tm == 1451988:
            text = evidence["noah"][0]["markdown"]
            require("ability rating of 35 " in text and "plays for Celta de Vigo" in text,
                    "Noah source profile changed.")
            raw = {key: int(value) for key, value in
                   re.findall(r"^\| ([A-Za-z ()]+) \| (\d+) \|$", text, re.MULTILINE)}
            require(len(raw) == 36, "Incomplete Noah attribute extraction.")
            # Dynamic potential is verified, but no numeric bound is evidenced.
            # NULL, never Anxo's PA or a guessed upper bound.
            block = {
                "version": "26.2.0", "rating": 35, "potential": None,
                "potential_range": None, "raw": {"attributes": raw},
            }
        else:
            original = next(p for p in provenance["quarantine"]
                            if p["tm"] == tm and p["original_fmi"]["value"] == uid)
            block = deepcopy(original["original_fminside_rating"])
        block["url"] = f"https://fminside.net/players/7-fm-26/{uid}-{slug}"
        block["identity_review"] = {
            "checked_at": CHECKED.isoformat(), "tm_id": tm,
            "fm_id": uid, "date_of_birth": dob,
            "dob_source_url": proof["url"],
            "report": "docs/import-pilot/laliga-fm-identities-2026-10-27.md",
        }
        result[tm] = block
    return result


def guard_state(players):
    ids = [p.pk for p in players]
    refs = [f"tm:{p.transfermarkt_id}" for p in players]
    queries = protected_queries()
    queries.update({
        "other_players": m.Player.objects.exclude(pk__in=ids),
        "other_external_ids": m.PlayerExternalId.objects.exclude(
            player_id__in=ids, source__code="FM"),
        "other_ratings": m.PlayerSourceRating.objects.exclude(player_id__in=ids, source="FM"),
        "other_snapshots": m.PlayerSourceRatingSnapshot.objects.exclude(
            player_id__in=ids, source__code="FM"),
        "other_strength": m.PlayerStrengthProfile.objects.exclude(player_id__in=ids),
        "other_issues": m.ImportIssue.objects.exclude(
            Q(entity="player", entity_ref__in=refs, field__startswith="ids.fmi")
            | Q(entity="player", entity_ref="tm:1451988",
                field="ratings.fminside.potential")),
        "import_packages": m.SourceImportRun.objects.all(),
    })
    state = {name: fingerprint(query) for name, query in queries.items()}
    allowed = {"fm_inside_id", "potential", "import_lock", "import_lock_reasons", "pool_status"}
    state["protected_target_fields"] = [
        {k: v for k, v in row.items() if k not in allowed}
        for row in m.Player.objects.filter(pk__in=ids).order_by("pk").values()
    ]
    state["target_strength_state"] = list(
        m.PlayerStrengthProfile.objects.filter(player_id__in=ids).order_by("player_id")
        .values("player_id", "freshness", "form_modifier"))
    return state


def changed_state(players):
    ids = [p.pk for p in players]
    refs = [f"tm:{p.transfermarkt_id}" for p in players]
    return {
        model._meta.label: fingerprint(query)
        for model, query in (
            (m.Player, m.Player.objects.filter(pk__in=ids)),
            (m.PlayerExternalId, m.PlayerExternalId.objects.filter(player_id__in=ids)),
            (m.PlayerSourceRating, m.PlayerSourceRating.objects.filter(player_id__in=ids)),
            (m.PlayerSourceRatingSnapshot,
             m.PlayerSourceRatingSnapshot.objects.filter(player_id__in=ids)),
            (m.PlayerStrengthProfile, m.PlayerStrengthProfile.objects.filter(player_id__in=ids)),
            (m.ImportIssue, m.ImportIssue.objects.filter(entity="player", entity_ref__in=refs)),
        )
    }


def correct(player, block):
    tm = player.transfermarkt_id
    uid, dob, _ = CONFIRMED[tm]
    require(str(player.date_of_birth) == dob, f"Workspace DOB differs: TM {tm}.")
    require(player.fm_inside_id in (None, uid), f"Existing FM identity differs: TM {tm}.")
    require(player.club and player.club.league.name == "LaLiga"
            and not player.club.league.is_playable and not league_started(player.club.league),
            "Correction is restricted to the non-playable, unstarted Workspace LaLiga.")
    require(not m.Player.objects.filter(fm_inside_id=uid).exclude(pk=player.pk).exists(),
            f"FM-ID {uid} already belongs to another player.")
    require(not m.PlayerExternalId.objects.filter(source__code="FM", external_id=str(uid))
            .exclude(player_id=player.pk).exists(), f"FM-ID {uid} has a competing owner.")
    open_locks = m.ImportIssue.objects.filter(
        entity="player", entity_ref=f"tm:{tm}", severity="player_lock", resolution_status="open")
    unrelated = open_locks.exclude(field__startswith="ids.fmi")
    if tm == 1451988:
        unrelated = unrelated.exclude(field="ratings.fminside.potential")
    require(not unrelated.exists(),
            f"Unrelated target-player lock must be reviewed separately: TM {tm}.")
    existing = m.PlayerExternalId.objects.filter(player=player, source__code="FM").first()
    if (player.fm_inside_id != uid or existing is None
            or existing.external_id != str(uid) or existing.status != "von_hand"
            or existing.checked_at != CHECKED):
        sync_ids(player, {"fmi": {
            "value": uid, "status": "von_hand", "checked_at": CHECKED.isoformat(),
            "match": "verified_uid_exact_dob",
        }}, SimpleNamespace())
    identity = m.PlayerExternalId.objects.get(player=player, source__code="FM")
    identity.profile_url = identity.source_url = block["url"]
    identity.match_evidence = block["identity_review"]
    identity.save(update_fields=["profile_url", "source_url", "match_evidence"])

    m.PlayerSourceRatingSnapshot.objects.get_or_create(
        player=player, source=source("FM"), recorded_at=CHECKED,
        source_version=block["version"], payload_hash=digest(block),
        defaults={"rating": block["rating"], "potential": block["potential"],
                  "raw_payload": block, "source_url": block["url"], "update_current": False})
    values = {
        "rating": block["rating"], "potential": block["potential"],
        "source_version": block["version"], "checked_at": CHECKED, "source_url": block["url"],
    }
    values.update({f.name: None for f in m.PlayerSourceRating._meta.fields
                   if f.get_internal_type() == "PositiveSmallIntegerField"
                   and f.name not in ("rating", "potential")})
    values.update(attributes(block, "fminside", player.position == "TW"))
    current = m.PlayerSourceRating.objects.filter(player=player, source="FM")
    if current.exists():
        current.update(**values)
    else:
        m.PlayerSourceRating.objects.bulk_create([
            m.PlayerSourceRating(player=player, source="FM", **values)])
    potentials = [r.potential for r in player.source_ratings.all() if r.potential is not None]
    player.potential = max(potentials) if potentials else None
    player.save(update_fields=["potential"])
    strength = compute_strength_for_player(player)
    require(strength["computable"] or (tm == 1451988 and block["potential"] is None),
            f"Verified source did not produce strength: TM {tm}.")
    profile = m.PlayerStrengthProfile.objects.filter(player=player).first()
    if not strength["computable"]:
        require(profile is None, "Incomplete source must not replace an existing strength.")
        run = m.SourceImportRun.objects.filter(club=player.owner_club or player.club).latest("pk")
        m.ImportIssue.objects.get_or_create(
            club=player.owner_club or player.club, entity="player",
            entity_ref=f"tm:{tm}", field="ratings.fminside.potential", subkey="",
            defaults={
                "package": run, "severity": "player_lock",
                "note": "FM-Identität über UID und Geburtsdatum bestätigt. "
                        "Dynamisches FM-Potenzial ohne belegte numerische Grenze; "
                        "keinen Wert erfinden. Stärke daher noch nicht berechenbar.",
                "external_reference": {"source_url": block["url"],
                                       "identity_review": block["identity_review"]},
            })
    elif profile is None:
        m.PlayerStrengthProfile.objects.create(player=player, base_strength=strength["base_strength"])
    elif profile.base_strength != strength["base_strength"]:
        profile.base_strength = strength["base_strength"]
        profile.save(update_fields=["base_strength"])
    # Preserve text/history, explicitly record the manual identity evidence.
    for row in m.ImportIssue.objects.filter(entity="player", entity_ref=f"tm:{tm}",
                                           field__startswith="ids.fmi",
                                           resolution_status="open"):
        row.resolution_status, row.resolved_at = "resolved", timezone.now()
        row.external_reference = dict(row.external_reference or {},
                                      identity_review=block["identity_review"])
        row.save(update_fields=["resolution_status", "resolved_at", "external_reference"])
    reasons = refresh_lock(player)
    require(reasons == (["Keine Stärke berechnet"] if tm == 1451988 else []),
            f"Unexpected remaining lock after correction: TM {tm}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    payloads = blocks()
    with transaction.atomic():
        players = list(m.Player.objects.select_for_update().filter(
            transfermarkt_id__in=CONFIRMED).order_by("pk"))
        require(len(players) == 3, "Expected exactly three confirmed players.")
        before = guard_state(players)
        for player in players:
            correct(player, payloads[player.transfermarkt_id])
        after = guard_state(players)
        # Newly created strength rows have no earlier freshness/form to preserve.
        before_strength = before.pop("target_strength_state")
        after_strength = after.pop("target_strength_state")
        require(before == after, "Protected data changed; rolling back.")
        require(all(row in after_strength for row in before_strength),
                "Existing form/freshness changed; rolling back.")
        initial = changed_state(players)
        for player in players:
            correct(player, payloads[player.transfermarkt_id])
        require(initial == changed_state(players), "Correction is not exactly replay-safe.")
        require(not m.Player.objects.filter(transfermarkt_id__in=set(QUARANTINE) - set(CONFIRMED))
                .exclude(fm_inside_id=None, import_lock=True).exists(),
                "One of the five retained quarantines was released.")
        require(not m.PlayerSourceRating.objects.filter(
            player__transfermarkt_id__in=set(QUARANTINE) - set(CONFIRMED), source="FM").exists(),
            "One of the five retained quarantines has an FM rating.")
        report = {
            "applied": args.apply, "protected_data_unchanged": True, "exact_replay": True,
            "confirmed": list(m.Player.objects.filter(pk__in=[p.pk for p in players])
                              .order_by("pk").values(
                                  "transfermarkt_id", "fm_inside_id", "import_lock", "potential")),
            "retained_quarantines": sorted(set(QUARANTINE) - set(CONFIRMED)),
            "noah_numeric_fm_potential": None,
        }
        if not args.apply:
            transaction.set_rollback(True)
    report_path = OUTPUT / ("fm-corrections-applied.json" if args.apply
                            else "fm-corrections-dry-run.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
