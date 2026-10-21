"""Guarded additive Workspace imports into the non-playable second league.

Uses the canonical package service unchanged. A batch is committed only after
identity, ownership, protected-state and exact-replay checks all succeed.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django
django.setup()

from django.apps import apps
from django.contrib.auth.models import User
from django.db import transaction
from game import models as m
from game.club_import.package_service import apply_package, identity, league_started
from game.club_import.package_validation import read_package, PackageError
from stadium_editor.models import StadiumDesign, StadiumGeometry


def fingerprint(queryset):
    checksum = hashlib.sha256()
    count = 0
    for row in queryset.order_by("pk").values().iterator(chunk_size=500):
        checksum.update(json.dumps(row, sort_keys=True, default=str).encode())
        checksum.update(b"\n")
        count += 1
    return count, checksum.hexdigest()


def protected_queries():
    # Existing anchors must not be overwritten even when real references become
    # resolvable. New club/stadium rows are permitted.
    models = [m.League, m.Club, m.Stadium, StadiumDesign, StadiumGeometry,
              m.ManagerProfile, User]
    queries = [model.objects.filter(pk__in=list(model.objects.values_list("pk", flat=True)))
               for model in models]
    for name in ("LeagueSeasonState", "GameSeasonState", "SimulatedMatch",
                 "FinanceTransaction", "ClubFinancialTransaction", "CoinTransaction"):
        queries.append(getattr(m, name).objects.all())
    return {q.model._meta.label: q for q in queries}


def import_batch(paths, owner_exceptions, apply=False):
    packages = [(Path(path), *read_package(Path(path))) for path in paths]
    club_tms = [manifest["club"]["tm_id"] for _, manifest, _ in packages]
    all_players = [p for _, _, data in packages for p in data["players"]]
    player_tms = [p["ids"]["tm"]["value"] for p in all_players]
    if len(set(club_tms)) != len(club_tms) or len(set(player_tms)) != len(player_tms):
        raise PackageError("Duplicate club/player identities in the submitted batch")
    report = {"applied": apply, "packages": [], "owner_exceptions": owner_exceptions}
    with transaction.atomic():
        league = m.League.objects.select_for_update().get(
            name="2. Bundesliga", country="Deutschland", level=2, is_playable=False)
        if league_started(league):
            raise PackageError("Second league has already started")
        protected = protected_queries()
        before = {key: fingerprint(q) for key, q in protected.items()}
        existing_player_ids = set(m.Player.objects.values_list("pk", flat=True))
        incoming_existing = {}
        for _, manifest, data in packages:
            club = identity(data["club"]["ids"], m.Club)
            if club and club.league_id != league.pk:
                raise PackageError("Existing target club belongs to another league")
            for pdata in data["players"]:
                player = identity(pdata["ids"], m.Player)
                if not player:
                    # Historic identities must never be silently stolen.
                    if m.PlayerExternalId.objects.filter(
                        source__code="TM", external_id=str(pdata["ids"]["tm"]["value"]),
                        identity_kind="spieler", person__isnull=False).exists():
                        raise PackageError("Historical identity needs explicit reconciliation")
                    continue
                if str(player.date_of_birth) != pdata["date_of_birth"]:
                    raise PackageError("Existing player has a contradictory birth date")
                if player.club_id and player.club.league.is_playable:
                    raise PackageError("Cannot initialize an active first-league player")
                tm = player.transfermarkt_id
                incoming_existing[tm] = player.pk
                expected_owner = (pdata["squad"].get("owner_club") or {}).get("tm_id")
                if (player.owner_club_tm_id is not None
                        and player.owner_club_tm_id != expected_owner
                        and owner_exceptions.get(tm) != player.owner_club_tm_id):
                    raise PackageError("Owner conflict requires explicit approval")
        # Exclude only incoming identities and already-known references to the
        # new clubs. Every other existing Player row must remain unchanged.
        from django.db.models import Q
        untouched = m.Player.objects.filter(pk__in=existing_player_ids).exclude(
            Q(pk__in=incoming_existing.values()) | Q(owner_club_tm_id__in=club_tms)
            | Q(loan_club_tm_id__in=club_tms))
        untouched_before = fingerprint(untouched)
        preserved = {}
        for player_tm, owner_tm in owner_exceptions.items():
            player = m.Player.objects.select_for_update().get(transfermarkt_id=player_tm)
            if player.owner_club_tm_id != owner_tm or player_tm not in incoming_existing:
                raise PackageError("Owner exception does not match the existing player")
            preserved[player_tm] = {
                "owner_club_id": player.owner_club_id,
                "owner_club_tm_id": player.owner_club_tm_id,
                "owner_club_original_name": player.owner_club_original_name,
            }
        for path, manifest, data in packages:
            result = apply_package(path, league)
            club = m.Club.objects.get(pk=result["club"])
            if club.league_id != league.pk or club.import_state != "nicht_spielbar":
                raise PackageError("Imported club has the wrong league/state")
            for pdata in data["players"]:
                tm = pdata["ids"]["tm"]["value"]
                if tm not in preserved:
                    continue
                m.Player.objects.filter(transfermarkt_id=tm).update(
                    **preserved[tm], loan_partner_club_id=preserved[tm]["owner_club_id"])
                m.ImportIssue.objects.get_or_create(
                    club=club, entity="player", entity_ref=f"tm:{tm}",
                    field="squad.owner_club", subkey="approved-existing-owner",
                    defaults={
                        "package_id": result["run"], "last_seen_package_id": result["run"],
                        "severity": "info",
                        "note": (
                            f"Freigegeben: bestehende Eigentümerschaft "
                            f"{preserved[tm]['owner_club_original_name']} "
                            f"(TM {preserved[tm]['owner_club_tm_id']}) beibehalten. "
                            f"Paketquelle nennt {pdata['squad']['owner_club']['name']} "
                            f"(TM {pdata['squad']['owner_club']['tm_id']}). "
                            f"Spieleridentität identisch; Leihe zu {club.name} übernommen."
                        ),
                        "external_reference": {"package_owner": pdata["squad"]["owner_club"],
                                               "preserved_owner": preserved[tm]},
                    })
            # Independently verify both mirror and canonical IDs for every row.
            players = []
            for pdata in data["players"]:
                tm = pdata["ids"]["tm"]["value"]
                player = m.Player.objects.get(transfermarkt_id=tm)
                for provider, code, field in (("tm", "TM", "transfermarkt_id"),
                                               ("fmi", "FM", "fm_inside_id")):
                    value = pdata["ids"][provider]["value"]
                    if value is not None:
                        if getattr(player, field) != value or not m.PlayerExternalId.objects.filter(
                                player=player, source__code=code, external_id=str(value),
                                identity_kind="spieler").exists():
                            raise PackageError("Imported player identity is incomplete")
                squad = pdata["squad"]
                expected_owner = owner_exceptions.get(tm, (squad.get("owner_club") or {}).get("tm_id"))
                expected_club = ((squad.get("loan_club") or {}).get("tm_id")
                                 if squad["status"] != "own" else expected_owner)
                resolved = m.Club.objects.filter(transfermarkt_id=expected_club).first()
                if player.owner_club_tm_id != expected_owner or player.club_id != (
                        resolved.pk if resolved else None):
                    raise PackageError("Imported player ownership or loan is incomplete")
                players.append(player)
            locked = sum(player.import_lock for player in players)
            explicit_locks = {g["ref"] for g in data["gaps"] if g["severity"] == "player_lock"}
            if not all(p.import_lock for p in players if f"tm:{p.transfermarkt_id}" in explicit_locks):
                raise PackageError("Explicit package player locks were not preserved")
            report["packages"].append({
                "club": club.name, "club_id": club.pk, "run": result["run"],
                "players": len(players), "new_players": sum(p.pk not in existing_player_ids for p in players),
                "first_team": manifest["counts"]["first_team"], "u21": manifest["counts"]["u21"],
                "persons": len(data["persons"]), "records": len(data["records"]),
                "titles": len(data["titles"]), "locked_players": locked,
                "strength_profiles": m.PlayerStrengthProfile.objects.filter(player__in=players).count(),
                "issues": dict(Counter(m.ImportIssue.objects.filter(club=club,
                            resolution_status="open").values_list("severity", flat=True))),
            })
        if fingerprint(untouched) != untouched_before:
            raise PackageError("Unrelated existing players changed")
        if any(fingerprint(q) != before[key] for key, q in protected.items()):
            raise PackageError("Protected club, season, stadium or financial state changed")
        # Replay must not alter any game/import row, not merely return a flag.
        game_models = [model for model in apps.get_models()
                       if model._meta.app_label in ("game", "stadium_editor")]
        first = {model._meta.label: fingerprint(model.objects.all()) for model in game_models}
        for path, _, _ in packages:
            if not apply_package(path, league)["unchanged"]:
                raise PackageError("Package replay was not idempotent")
        if any(fingerprint(model.objects.all()) != first[model._meta.label] for model in game_models):
            raise PackageError("Package replay changed persisted data")
        report.update(protected_state_unchanged=True, replay_unchanged=True,
                      unrelated_players_unchanged=True, league_playable=False)
        if not apply:
            transaction.set_rollback(True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packages", nargs="+")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preserve-owner", action="append", default=[],
                        help="Explicitly approved PLAYER_TM:OWNER_TM mapping")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    exceptions = dict(tuple(map(int, value.split(":"))) for value in args.preserve_owner)
    report = import_batch(args.packages, exceptions, apply=args.apply)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
